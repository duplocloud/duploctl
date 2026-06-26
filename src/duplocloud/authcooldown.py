import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

AUTH_COOLDOWN_ENV_VAR = "DUPLO_AUTH_COOLDOWN"
AUTH_COOLDOWN_DEFAULT_DURATION = 60 * 60  # 60 minutes in seconds

logger = logging.getLogger("duplo.authcooldown")


@dataclass
class CooldownResult:
  """Result from a cooldown check or wait operation.

  Exactly one of token, error, or retry should be set.
  """
  token: str | None = None
  error: str | None = None
  retry: bool = False


def get_host_cache_key(host: str) -> str:
  """Extract hostname from a URL for use as a cache key.

  Args:
    host: The full URL of the host.

  Returns:
    The hostname portion of the URL.
  """
  if "://" in host:
    return host.split("://")[1].replace("/", "")
  return host.replace("/", "")


def is_auth_cooldown_enabled(val=None) -> tuple[int, bool]:
  """Check whether auth cooldown is enabled.

  Args:
    val: Explicit cooldown value (from CLI arg). Falls back to
      DUPLO_AUTH_COOLDOWN env var when None.

  Values: "true"/"1" -> 60m default, valid duration string (e.g. "30m") -> parsed,
  unset/"false"/"0" -> disabled.

  Returns:
    A tuple of (duration_seconds, enabled).
  """
  if val is None:
    val = os.environ.get(AUTH_COOLDOWN_ENV_VAR, "")
  if not val:
    return 0, False

  lower = val.lower()
  if lower in ("false", "0", "no", "off"):
    return 0, False
  if lower in ("true", "1", "yes", "on"):
    return AUTH_COOLDOWN_DEFAULT_DURATION, True

  duration = _parse_duration(val)
  if duration is None or duration <= 0:
    return 0, False
  return duration, True


def _parse_duration(val: str) -> int | None:
  """Parse a duration string like '30m', '2h', '90s' into seconds.

  Args:
    val: Duration string.

  Returns:
    Duration in seconds, or None if invalid.
  """
  val = val.strip()
  if not val:
    return None

  suffixes = {"s": 1, "m": 60, "h": 3600}
  if val[-1].lower() in suffixes:
    try:
      num = float(val[:-1])
      return int(num * suffixes[val[-1].lower()])
    except ValueError:
      return None

  try:
    return int(float(val))
  except ValueError:
    return None


def _auth_cooldown_path(cache_dir: str, host: str, admin: bool) -> str:
  """Return the path to the cooldown file for the given host URL and admin flag.

  The cooldown file is stored in the same cache directory as credential caches.

  Args:
    cache_dir: The cache directory path.
    host: The host URL.
    admin: Whether this is an admin request.

  Returns:
    The full path to the cooldown file.
  """
  os.makedirs(cache_dir, mode=0o700, exist_ok=True)

  hostname = get_host_cache_key(host)
  suffix = ".admin.cooldown" if admin else ".cooldown"
  return os.path.join(cache_dir, hostname + suffix)


def _read_info_from_path(path: str) -> dict | None:
  """Read cooldown info from a file path.

  Args:
    path: Path to the cooldown file.

  Returns:
    The cooldown info dict, or None if unreadable.
  """
  try:
    with open(path, "r") as f:
      return json.load(f)
  except (OSError, json.JSONDecodeError):
    return None


def read_cooldown_info(cache_dir: str, host: str, admin: bool) -> dict | None:
  """Read the cooldown file for the given host and admin flag.

  Args:
    cache_dir: The cache directory path.
    host: The host URL.
    admin: Whether this is an admin request.

  Returns:
    The cooldown info dict, or None if no cooldown file exists.
  """
  try:
    path = _auth_cooldown_path(cache_dir, host, admin)
  except OSError:
    return None
  return _read_info_from_path(path)


def try_set_auth_cooldown(cache_dir: str, host: str, port: int, admin: bool, cooldown_duration: int) -> tuple[bool, datetime | None, str | None]:
  """Atomically create a cooldown file for the given host and admin flag.

  Returns (True, None, None) if the cooldown was set (caller should open the browser),
  (False, expiry, None) if a recent cooldown is already active,
  or (False, None, error_msg) on unexpected errors.

  Stale cooldowns (older than cooldown_duration) are automatically replaced.

  Args:
    cache_dir: The cache directory path.
    host: The host URL.
    port: The local port being listened on.
    admin: Whether this is an admin request.
    cooldown_duration: The cooldown duration in seconds.

  Returns:
    A tuple of (acquired, expiry, error).
  """
  try:
    cooldown_path = _auth_cooldown_path(cache_dir, host, admin)
  except OSError as e:
    return False, None, f"failed to get cooldown path: {e}"

  return _try_set_cooldown(cooldown_path, port, admin, cooldown_duration, retry_on_stale=True)


def _try_set_cooldown(cooldown_path: str, port: int, admin: bool, cooldown_duration: int, retry_on_stale: bool) -> tuple[bool, datetime | None, str | None]:
  """Internal implementation of cooldown file creation with stale retry logic."""
  info = {
    "pid": os.getpid(),
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "port": port,
    "admin": admin,
  }

  try:
    fd = os.open(cooldown_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
  except FileExistsError:
    existing = _read_info_from_path(cooldown_path)
    if retry_on_stale and (existing is None or _is_stale(existing, cooldown_duration)):
      tmp_path = f"{cooldown_path}.stale.{os.getpid()}"
      try:
        os.rename(cooldown_path, tmp_path)
        os.remove(tmp_path)
      except OSError:
        pass
      return _try_set_cooldown(cooldown_path, port, admin, cooldown_duration, retry_on_stale=False)

    expiry = None
    if existing:
      try:
        ts = datetime.fromisoformat(existing["timestamp"])
        expiry = ts + timedelta(seconds=cooldown_duration)
      except (KeyError, ValueError):
        pass
    return False, expiry, None
  except OSError as e:
    return False, None, f"failed to create cooldown file: {e}"

  try:
    with os.fdopen(fd, "w") as f:
      json.dump(info, f)
  except OSError:
    try:
      os.remove(cooldown_path)
    except OSError:
      pass
    return False, None, "failed to write cooldown file"

  return True, None, None


def _is_stale(info: dict, cooldown_duration: int) -> bool:
  """Check if a cooldown info dict is stale (older than cooldown_duration)."""
  try:
    ts = datetime.fromisoformat(info["timestamp"])
    return (datetime.now(timezone.utc) - ts).total_seconds() > cooldown_duration
  except (KeyError, ValueError):
    return True


def update_cooldown(cache_dir: str, host: str, admin: bool, port: int) -> None:
  """Rewrite the cooldown file with the current PID and port, preserving the original timestamp.

  Used when a relay process takes over a dead process's port.

  Args:
    cache_dir: The cache directory path.
    host: The host URL.
    admin: Whether this is an admin request.
    port: The new port to write.
  """
  existing = read_cooldown_info(cache_dir, host, admin)
  ts = datetime.now(timezone.utc).isoformat()
  if existing and "timestamp" in existing:
    ts = existing["timestamp"]

  info = {
    "pid": os.getpid(),
    "timestamp": ts,
    "port": port,
    "admin": admin,
  }

  try:
    cooldown_path = _auth_cooldown_path(cache_dir, host, admin)
    with open(cooldown_path, "w") as f:
      json.dump(info, f)
  except OSError as e:
    logger.warning("auth cooldown: failed to update cooldown for relay: %s", e)


def clear_auth_cooldown(cache_dir: str, host: str, admin: bool) -> None:
  """Remove the cooldown file for the given host and admin flag.

  Called after authentication completes or fails. No-op if the file doesn't exist.

  Args:
    cache_dir: The cache directory path.
    host: The host URL.
    admin: Whether this is an admin request.
  """
  try:
    cooldown_path = _auth_cooldown_path(cache_dir, host, admin)
    os.remove(cooldown_path)
  except OSError:
    pass


def clear_all_caches(cache_dir: str = None) -> int:
  """Remove all cached credentials and auth cooldown files.

  Both credential caches and cooldown files live in the same cache directory.

  Args:
    cache_dir: The duploctl cache directory (e.g. ~/.duplo/cache).

  Returns:
    The number of files removed.
  """
  count = 0
  if not cache_dir or not os.path.isdir(cache_dir):
    return count

  try:
    for entry in os.listdir(cache_dir):
      path = os.path.join(cache_dir, entry)
      if os.path.isfile(path):
        try:
          os.remove(path)
          count += 1
        except OSError:
          pass
  except OSError:
    pass

  return count


def is_pid_alive(pid: int) -> bool:
  """Check whether a process with the given PID is still running.

  Args:
    pid: The process ID to check.

  Returns:
    True if the process is alive, False otherwise.
  """
  if pid <= 0:
    return False
  try:
    os.kill(pid, 0)
    return True
  except PermissionError:
    return True
  except (OSError, ProcessLookupError):
    return False


def wait_for_pid_exit(pid: int, timeout: float, poll_interval: float = 0.5) -> bool:
  """Poll until the given PID exits or the timeout is reached.

  Args:
    pid: The process ID to wait for.
    timeout: Maximum time to wait in seconds.
    poll_interval: Time between polls in seconds.

  Returns:
    True if the PID exited, False if the timeout was reached.
  """
  deadline = time.monotonic() + timeout
  while time.monotonic() < deadline:
    if not is_pid_alive(pid):
      return True
    time.sleep(poll_interval)
  return not is_pid_alive(pid)


def is_tty() -> bool:
  """Check if stderr is connected to a terminal (TTY).

  Returns:
    True if stderr is a TTY.
  """
  try:
    return os.isatty(sys.stderr.fileno())
  except (AttributeError, ValueError):
    return False


def check_cooldown_before_listen(cache_dir: str, host: str, admin: bool, default_port: int, cooldown_duration: int, get_cached_token: callable = None) -> tuple[int, bool, int, CooldownResult | None]:
  """Evaluate existing cooldown state and decide how to proceed.

  Args:
    cache_dir: The cache directory path.
    host: The host URL.
    admin: Whether this is an admin request.
    default_port: The default port to listen on.
    cooldown_duration: The cooldown duration in seconds.
    get_cached_token: Optional callable that returns a cached token string or None.

  Returns:
    A tuple of (listen_port, open_browser, timeout, early_result).
    early_result is a CooldownResult if caller should return immediately, or None.
  """
  listen_port = default_port
  open_browser = True
  timeout = cooldown_duration

  info = read_cooldown_info(cache_dir, host, admin)
  if info is None:
    return listen_port, open_browser, timeout, None

  try:
    ts = datetime.fromisoformat(info["timestamp"])
  except (KeyError, ValueError):
    clear_auth_cooldown(cache_dir, host, admin)
    return listen_port, open_browser, timeout, None

  remaining = cooldown_duration - (datetime.now(timezone.utc) - ts).total_seconds()
  if remaining <= 0:
    clear_auth_cooldown(cache_dir, host, admin)
    return listen_port, open_browser, timeout, None

  pid = info.get("pid", 0)
  if is_pid_alive(pid):
    result = _wait_for_cooldown_holder(cache_dir, host, admin, default_port, info, cooldown_duration, get_cached_token)
    return default_port, True, cooldown_duration, result

  logger.info("auth cooldown: previous process (PID %d) is dead, attempting relay on port %d",
        pid, info.get("port", 0))
  return info.get("port", default_port), False, remaining, None


def recover_relay_bind_failure(cache_dir: str, host: str, admin: bool, default_port: int, relay_port: int, cooldown_duration: int, get_cached_token: callable = None) -> CooldownResult:
  """Handle the case where binding the relay port failed.

  Re-checks whether another relay process took over, or resets for a fresh start.

  Args:
    cache_dir: The cache directory path.
    host: The host URL.
    admin: Whether this is an admin request.
    default_port: The default port to listen on.
    relay_port: The relay port that failed to bind.
    cooldown_duration: The cooldown duration in seconds.
    get_cached_token: Optional callable that returns a cached token string or None.

  Returns:
    A CooldownResult with token, error, or retry.
  """
  info = read_cooldown_info(cache_dir, host, admin)
  if info and is_pid_alive(info.get("pid", 0)):
    return _wait_for_cooldown_holder(cache_dir, host, admin, default_port, info, cooldown_duration, get_cached_token)

  logger.info("auth cooldown: port %d unavailable, resetting cooldown", relay_port)
  clear_auth_cooldown(cache_dir, host, admin)
  return CooldownResult(retry=True)


def acquire_or_update_cooldown(cache_dir: str, host: str, admin: bool, default_port: int, local_port: int, open_browser: bool, cooldown_duration: int, get_cached_token: callable = None) -> CooldownResult | None:
  """Atomically set a new cooldown (fresh start) or update an existing one (relay).

  Args:
    cache_dir: The cache directory path.
    host: The host URL.
    admin: Whether this is an admin request.
    default_port: The default port.
    local_port: The port the listener is actually on.
    open_browser: Whether a browser should be opened.
    cooldown_duration: The cooldown duration in seconds.
    get_cached_token: Optional callable that returns a cached token string or None.

  Returns:
    None if the caller should continue, or a CooldownResult if it should return.
  """
  if open_browser:
    acquired, expiry, err = try_set_auth_cooldown(cache_dir, host, local_port, admin, cooldown_duration)
    if err:
      return CooldownResult(error=f"auth cooldown error: {err}")
    if not acquired:
      info = read_cooldown_info(cache_dir, host, admin)
      if info:
        return _wait_for_cooldown_holder(cache_dir, host, admin, default_port, info, cooldown_duration, get_cached_token)
      expiry_str = expiry.isoformat() if expiry else "unknown"
      return CooldownResult(error=(
        f"authentication for {get_host_cache_key(host)} was recently attempted (expires {expiry_str})\n"
        f"To force a new attempt: duploctl cache clear  (or unset {AUTH_COOLDOWN_ENV_VAR} to disable cooldown)"
      ))
  else:
    update_cooldown(cache_dir, host, admin, local_port)
  return None


def _cached_token_result(get_cached_token: callable = None) -> CooldownResult | None:
  """Return a token result from the credential cache, or None if unavailable.

  Args:
    get_cached_token: Optional callable that returns a cached token string or None.

  Returns:
    A CooldownResult with token, or None.
  """
  if not get_cached_token:
    return None
  token = get_cached_token()
  if not token:
    return None
  logger.info("auth cooldown: using cached credentials from completed auth process")
  return CooldownResult(token=token)


def _wait_for_cooldown_holder(cache_dir: str, host: str, admin: bool, default_port: int, info: dict, cooldown_duration: int, get_cached_token: callable = None) -> CooldownResult:
  """Wait for the active cooldown holder to finish, then retry.

  Args:
    cache_dir: The cache directory path.
    host: The host URL.
    admin: Whether this is an admin request.
    default_port: The default port.
    info: The cooldown info dict.
    cooldown_duration: The cooldown duration in seconds.
    get_cached_token: Optional callable that returns a cached token string or None.

  Returns:
    A CooldownResult with token, error, or retry.
  """
  try:
    ts = datetime.fromisoformat(info["timestamp"])
  except (KeyError, ValueError):
    clear_auth_cooldown(cache_dir, host, admin)
    return CooldownResult(retry=True)

  remaining = cooldown_duration - (datetime.now(timezone.utc) - ts).total_seconds()
  if remaining <= 0:
    clear_auth_cooldown(cache_dir, host, admin)
    result = _cached_token_result(get_cached_token)
    if result:
      return result
    return CooldownResult(retry=True)

  pid = info.get("pid", 0)
  logger.info("auth cooldown: waiting for active auth process (PID %d, port %d) to complete (up to %ds)",
        pid, info.get("port", 0), int(remaining))

  if wait_for_pid_exit(pid, remaining, 0.5):
    result = _cached_token_result(get_cached_token)
    if result:
      return result
    return CooldownResult(retry=True)

  return CooldownResult(error=(
    f"authentication for {get_host_cache_key(host)} is being handled by another process (PID {pid}) which has not completed\n"
    f"To force a new attempt: duploctl cache clear  (or unset {AUTH_COOLDOWN_ENV_VAR} to disable cooldown)"
  ))
