"""Local Duplo config file management.

Owns loading, context resolution, and atomic writes for the duploctl
config file (default ``~/.duplo/config``). Consumed by both the
``DuploCtl`` controller (read path) and the ``config`` CLI resource
(read/write path). Concurrent writers are last-writer-wins; the atomic
replace only guarantees readers never see a torn file.
"""
import os
import yaml
from .errors import DuploError

VALID_CONTEXT_KEYS = (
  "host", "token", "tenant", "workspace",
  "interactive", "admin", "nocache",
  "environment", "resource_group", "helpdesk_host", "helpdesk_token",
)
"""Context keys the config resource may get/set/unset.

``name`` is deliberately excluded: it is the context identifier, not a
setting. New keys (e.g. for the AI HelpDesk) must be added here before
``duploctl config set`` will accept them.
"""

BOOLEAN_CONTEXT_KEYS = ("interactive", "admin", "nocache")


def _atomic_write_yaml(path: str, data: dict) -> None:
  """Write YAML to a file atomically via a temp file and rename.

  Concurrent readers never observe a truncated or partially written
  file. The file is chmodded 0o600 because it may hold tokens.

  Args:
    path: The destination file path.
    data: The dict to serialize.
  """
  tmp_path = f"{path}.tmp.{os.getpid()}"
  with open(tmp_path, "w") as f:
    yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
  os.chmod(tmp_path, 0o600)
  os.replace(tmp_path, path)


class DuploConfig():
  """Duplo Config Store

  Loads and saves the duploctl config file and resolves contexts within
  it. The parsed document is cached after first read; ``save()``
  refreshes the cache so readers sharing this instance never go stale.
  """

  def __init__(self, path: str):
    self.path = path
    self._data = None

  @property
  def data(self) -> dict:
    """The parsed config document, lazily loaded and cached.

    Raises:
      DuploError: If the config file does not exist.
    """
    if self._data is None:
      if not os.path.exists(self.path):
        raise DuploError("Duplo config not found", 500)
      with open(self.path, "r") as f:
        self._data = yaml.safe_load(f)
    return self._data

  def exists(self) -> bool:
    """Check if the config file exists on disk."""
    return os.path.exists(self.path)

  def scaffold(self) -> dict:
    """Return an empty config document for a fresh install."""
    return {"current-context": None, "contexts": []}

  def save(self, data: dict = None) -> None:
    """Atomically write the config document and refresh the cache.

    Args:
      data: The document to write. Defaults to the cached document.
    """
    if data is None:
      data = self.data
    parent = os.path.dirname(os.path.abspath(self.path))
    os.makedirs(parent, exist_ok=True)
    _atomic_write_yaml(self.path, data)
    self._data = data

  def current_context_name(self, override: str = None) -> str:
    """Resolve the name of the context to operate on.

    Args:
      override: An explicit context name (the ``--ctx`` flag) which
        wins over the file's ``current-context``.

    Returns:
      The context name.

    Raises:
      DuploError: If no context is selected anywhere.
    """
    ctx = override if override else self.data.get("current-context", None)
    if ctx is None:
      raise DuploError(
        "Duplo context not set, please set 'current-context' to a portals name in your config", 500)
    return ctx

  def get_context(self, name: str = None) -> dict:
    """Get a context from the config by name.

    Args:
      name: The context name. Defaults to the current context.

    Returns:
      The context as a dict.

    Raises:
      DuploError: If the context is not selected or not found.
    """
    ctx = self.current_context_name(name)
    contexts = self.data.get("contexts", None) or []
    try:
      return [c for c in contexts if c["name"] == ctx][0]
    except IndexError:
      raise DuploError(f"Portal '{ctx}' not found in config", 500)

  def set_current_context(self, name: str) -> None:
    """Switch the file's ``current-context`` to an existing context.

    Args:
      name: The context name to switch to.

    Raises:
      DuploError: If no such context exists in the config.
    """
    self.get_context(name)
    self.data["current-context"] = name
    self.save()

  def validate_key(self, key: str) -> str:
    """Validate a context key against the strict allowlist.

    Args:
      key: The key to validate.

    Returns:
      The key, unchanged.

    Raises:
      DuploError: If the key is not an allowed context key.
    """
    if key not in VALID_CONTEXT_KEYS:
      raise DuploError(
        f"Invalid config key '{key}'. Valid keys: {', '.join(VALID_CONTEXT_KEYS)}", 400)
    return key

  def get_key(self, key: str, ctx_name: str = None):
    """Get a key's value from a context.

    Args:
      key: The context key to read.
      ctx_name: The context name. Defaults to the current context.

    Returns:
      The value, or None if the key is not set.
    """
    self.validate_key(key)
    return self.get_context(ctx_name).get(key, None)

  def set_key(self, key: str, value, ctx_name: str = None) -> str:
    """Set a key's value in a context and save the file.

    If the target context does not exist it is created (upsert); when
    the file itself is missing an explicit ``ctx_name`` is required to
    scaffold it. ``current-context`` is set to the new context only if
    it was previously unset. Boolean keys coerce ``true``/``false``
    strings (case-insensitively).

    Args:
      key: The context key to set.
      value: The value to set.
      ctx_name: The context name. Defaults to the current context.

    Returns:
      The name of the context that was written.

    Raises:
      DuploError: If the key is invalid, a boolean key gets a
        non-boolean value, or no context can be determined.
    """
    self.validate_key(key)
    if key in BOOLEAN_CONTEXT_KEYS:
      value = self._coerce_bool(key, value)
    if not self.exists():
      if ctx_name is None:
        raise DuploError(
          "No context selected; pass --ctx <name> to create or target a context", 400)
      self._data = self.scaffold()
    data = self.data
    ctx = self.current_context_name(ctx_name)
    contexts = data.get("contexts", None) or []
    data["contexts"] = contexts
    target = next((c for c in contexts if c.get("name") == ctx), None)
    if target is None:
      target = {"name": ctx}
      contexts.append(target)
    target[key] = value
    if data.get("current-context", None) is None:
      data["current-context"] = ctx
    self.save(data)
    return ctx

  def unset_key(self, key: str, ctx_name: str = None) -> str:
    """Remove a key from a context and save the file.

    Removing a key that is not set is a no-op success.

    Args:
      key: The context key to remove.
      ctx_name: The context name. Defaults to the current context.

    Returns:
      The name of the context that was written.
    """
    self.validate_key(key)
    target = self.get_context(ctx_name)
    if key in target:
      del target[key]
      self.save()
    return target["name"]

  def _coerce_bool(self, key: str, value) -> bool:
    """Coerce a boolean key's value to a bool.

    Args:
      key: The key being set, for the error message.
      value: The raw value, a bool or a true/false string.

    Raises:
      DuploError: If the value is not a recognizable boolean.
    """
    if isinstance(value, bool):
      return value
    if isinstance(value, str) and value.lower() in ("true", "false"):
      return value.lower() == "true"
    raise DuploError(
      f"Invalid value '{value}' for boolean key '{key}': use true or false", 400)
