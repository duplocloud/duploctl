import copy

from duplocloud.commander import Resource, Command
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResource
import duplocloud.args as args

REDACTED_KEYS = ("token", "helpdesk_token")


@Resource("config", client=None)
class DuploConfigResource(DuploResource):
  """Config Resource

  Manage the local duploctl config file (default ``~/.duplo/config``):
  view it, read/write keys on the current context, and switch the
  current context. Not to be confused with ``duploctl tenant config``,
  which edits tenant metadata through the portal API.
  """
  def __init__(self, duplo):
    super().__init__(duplo)
    self.store = duplo.config_store

  @Command()
  def view(self) -> dict:
    """Show the full config with secrets redacted.

    Token values are replaced with ``REDACTED``; use
    ``duploctl config get token`` for the real value.

    Usage: CLI Usage
      ```sh
      duploctl config view
      ```

    Returns:
      config: The config document with tokens redacted.
    """
    doc = copy.deepcopy(self.store.data)
    for ctx in doc.get("contexts", None) or []:
      for key in REDACTED_KEYS:
        if key in ctx:
          ctx[key] = "REDACTED"
    return doc

  @Command()
  def get(self, key: args.CONFIG_KEY) -> dict:
    """Get a key's value from the current context.

    Targets the context chosen by ``--ctx`` when given, otherwise the
    file's ``current-context``. Values are returned unredacted.

    Usage: CLI Usage
      ```sh
      duploctl config get workspace
      ```

    Args:
      key: The config context key to read.

    Returns:
      result: The context name and the key's value.

    Raises:
      DuploError: If the key is invalid or no context is selected.
    """
    ctx = self.store.current_context_name(self.duplo._context)
    return {"context": ctx, key: self.store.get_key(key, ctx)}

  @Command()
  def set(self, key: args.CONFIG_KEY, value: args.CONFIG_VALUE) -> dict:
    """Set a key's value in the current context.

    Targets the context chosen by ``--ctx`` when given, otherwise the
    file's ``current-context``. A missing context is created, and a
    missing config file is scaffolded when ``--ctx`` names the context
    to create. Rewriting the file removes any YAML comments in it.

    Usage: CLI Usage
      ```sh
      duploctl config set workspace my-workspace
      duploctl --ctx myportal config set host https://myportal.duplocloud.net
      ```

    Args:
      key: The config context key to set.
      value: The value to set.

    Returns:
      message: Which key was set in which context.

    Raises:
      DuploError: If the key is invalid or no context is selected.
    """
    ctx = self.store.set_key(key, value, self.duplo._context)
    return {"message": f"set {key} in context '{ctx}'"}

  @Command()
  def unset(self, key: args.CONFIG_KEY) -> dict:
    """Remove a key from the current context.

    Targets the context chosen by ``--ctx`` when given, otherwise the
    file's ``current-context``. Removing an absent key succeeds.

    Usage: CLI Usage
      ```sh
      duploctl config unset workspace
      ```

    Args:
      key: The config context key to remove.

    Returns:
      message: Which key was removed from which context.

    Raises:
      DuploError: If the key is invalid or no context is selected.
    """
    ctx = self.store.unset_key(key, self.duplo._context)
    return {"message": f"unset {key} in context '{ctx}'"}

  @Command()
  def use(self, name: args.NAME = None) -> dict:
    """Switch the current context.

    Sets the file's ``current-context`` to an existing context.

    Usage: CLI Usage
      ```sh
      duploctl config use myportal
      ```

    Args:
      name: The name of the context to switch to.

    Returns:
      message: The context switched to.

    Raises:
      DuploError: If no name is given or the context does not exist.
    """
    if not name:
      raise DuploError("A context name is required", 400)
    self.store.set_current_context(name)
    return {"message": f"switched to context '{name}'"}
