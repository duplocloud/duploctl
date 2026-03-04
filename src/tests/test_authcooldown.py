import json
import os
import time
import pytest
from datetime import datetime, timezone, timedelta

from duplocloud.authcooldown import (
  AUTH_COOLDOWN_ENV_VAR,
  AUTH_COOLDOWN_DEFAULT_DURATION,
  CooldownResult,
  is_auth_cooldown_enabled,
  _parse_duration,
  _auth_cooldown_path,
  read_cooldown_info,
  try_set_auth_cooldown,
  update_cooldown,
  clear_auth_cooldown,
  clear_all_caches,
  is_pid_alive,
  wait_for_pid_exit,
  is_tty,
  get_host_cache_key,
  check_cooldown_before_listen,
  recover_relay_bind_failure,
  acquire_or_update_cooldown,
  _cached_token_result,
  _wait_for_cooldown_holder,
  _try_set_cooldown,
)


# --- Helpers & Fixtures ---

def setup_test_host(tmp_path, hostname="test.example.com"):
  """Return (host, cache_dir) using a temp directory so tests don't pollute the real filesystem."""
  cache_dir = str(tmp_path / "cache")
  return f"https://{hostname}", cache_dir


def write_fake_cooldown(cache_dir, host, admin, pid, port, timestamp):
  """Create a cooldown file with the given parameters for testing."""
  cooldown_path = _auth_cooldown_path(cache_dir, host, admin)
  info = {
    "pid": pid,
    "timestamp": timestamp.isoformat(),
    "port": port,
    "admin": admin,
  }
  with open(cooldown_path, "w") as f:
    json.dump(info, f)


def must_set_cooldown(cache_dir, host, port, admin, duration):
  """Call try_set_auth_cooldown and assert it succeeds."""
  ok, _, err = try_set_auth_cooldown(cache_dir, host, port, admin, duration)
  assert err is None, f"unexpected error setting cooldown: {err}"
  assert ok, "expected cooldown set to succeed"


# --- Tests for is_auth_cooldown_enabled ---

@pytest.mark.unit
class TestIsAuthCooldownEnabled:
  def test_unset(self, monkeypatch):
    monkeypatch.delenv(AUTH_COOLDOWN_ENV_VAR, raising=False)
    dur, enabled = is_auth_cooldown_enabled()
    assert not enabled
    assert dur == 0

  def test_empty(self, monkeypatch):
    monkeypatch.setenv(AUTH_COOLDOWN_ENV_VAR, "")
    dur, enabled = is_auth_cooldown_enabled()
    assert not enabled
    assert dur == 0

  def test_true(self, monkeypatch):
    monkeypatch.setenv(AUTH_COOLDOWN_ENV_VAR, "true")
    dur, enabled = is_auth_cooldown_enabled()
    assert enabled
    assert dur == AUTH_COOLDOWN_DEFAULT_DURATION

  def test_1(self, monkeypatch):
    monkeypatch.setenv(AUTH_COOLDOWN_ENV_VAR, "1")
    dur, enabled = is_auth_cooldown_enabled()
    assert enabled
    assert dur == AUTH_COOLDOWN_DEFAULT_DURATION

  def test_yes(self, monkeypatch):
    monkeypatch.setenv(AUTH_COOLDOWN_ENV_VAR, "yes")
    dur, enabled = is_auth_cooldown_enabled()
    assert enabled

  def test_on(self, monkeypatch):
    monkeypatch.setenv(AUTH_COOLDOWN_ENV_VAR, "on")
    dur, enabled = is_auth_cooldown_enabled()
    assert enabled

  def test_false(self, monkeypatch):
    monkeypatch.setenv(AUTH_COOLDOWN_ENV_VAR, "false")
    _, enabled = is_auth_cooldown_enabled()
    assert not enabled

  def test_0(self, monkeypatch):
    monkeypatch.setenv(AUTH_COOLDOWN_ENV_VAR, "0")
    _, enabled = is_auth_cooldown_enabled()
    assert not enabled

  def test_no(self, monkeypatch):
    monkeypatch.setenv(AUTH_COOLDOWN_ENV_VAR, "no")
    _, enabled = is_auth_cooldown_enabled()
    assert not enabled

  def test_off(self, monkeypatch):
    monkeypatch.setenv(AUTH_COOLDOWN_ENV_VAR, "off")
    _, enabled = is_auth_cooldown_enabled()
    assert not enabled

  def test_30m(self, monkeypatch):
    monkeypatch.setenv(AUTH_COOLDOWN_ENV_VAR, "30m")
    dur, enabled = is_auth_cooldown_enabled()
    assert enabled
    assert dur == 30 * 60

  def test_2h(self, monkeypatch):
    monkeypatch.setenv(AUTH_COOLDOWN_ENV_VAR, "2h")
    dur, enabled = is_auth_cooldown_enabled()
    assert enabled
    assert dur == 2 * 3600

  def test_garbage(self, monkeypatch):
    monkeypatch.setenv(AUTH_COOLDOWN_ENV_VAR, "notaduration")
    _, enabled = is_auth_cooldown_enabled()
    assert not enabled

  def test_negative(self, monkeypatch):
    monkeypatch.setenv(AUTH_COOLDOWN_ENV_VAR, "-5m")
    _, enabled = is_auth_cooldown_enabled()
    assert not enabled


# --- Tests for parse_duration ---

@pytest.mark.unit
class TestParseDuration:
  def test_seconds(self):
    assert _parse_duration("90s") == 90

  def test_minutes(self):
    assert _parse_duration("30m") == 1800

  def test_hours(self):
    assert _parse_duration("2h") == 7200

  def test_plain_number(self):
    assert _parse_duration("120") == 120

  def test_invalid(self):
    assert _parse_duration("abc") is None

  def test_empty(self):
    assert _parse_duration("") is None


# --- Tests for cooldown file operations ---

@pytest.mark.unit
class TestTrySetAuthCooldown:
  def test_first_set_succeeds(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    must_set_cooldown(cache_dir, host, 8080, False, 3600)

  def test_second_set_blocked(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    must_set_cooldown(cache_dir, host, 8080, False, 3600)

    ok, _, err = try_set_auth_cooldown(cache_dir, host, 9090, False, 3600)
    assert err is None
    assert not ok, "expected second set to be blocked by active cooldown"

  def test_stale_cooldown_replaced(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_duration = 3600

    # Create a stale cooldown file manually.
    write_fake_cooldown(cache_dir, host, False, 99999, 7777,
              datetime.now(timezone.utc) - timedelta(seconds=cooldown_duration + 1))

    ok, _, err = try_set_auth_cooldown(cache_dir, host, 8080, False, cooldown_duration)
    assert err is None
    assert ok, "expected stale cooldown to be replaced"

    # Verify the new cooldown has our PID.
    info = read_cooldown_info(cache_dir, host, False)
    assert info["pid"] == os.getpid()

  def test_different_hosts_independent(self, tmp_path):
    host1, cache_dir = setup_test_host(tmp_path, "host1.example.com")
    host2, _ = setup_test_host(tmp_path, "host2.example.com")
    must_set_cooldown(cache_dir, host1, 8080, False, 3600)
    must_set_cooldown(cache_dir, host2, 9090, False, 3600)

  def test_admin_flag_independent(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    must_set_cooldown(cache_dir, host, 8080, False, 3600)
    must_set_cooldown(cache_dir, host, 9090, True, 3600)


# --- Tests for clear_auth_cooldown ---

@pytest.mark.unit
class TestClearAuthCooldown:
  def test_removes_file(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    must_set_cooldown(cache_dir, host, 8080, False, 3600)

    cooldown_path = _auth_cooldown_path(cache_dir, host, False)
    assert os.path.exists(cooldown_path)

    clear_auth_cooldown(cache_dir, host, False)
    assert not os.path.exists(cooldown_path)

  def test_allows_reacquire(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    must_set_cooldown(cache_dir, host, 8080, False, 3600)
    clear_auth_cooldown(cache_dir, host, False)
    must_set_cooldown(cache_dir, host, 9090, False, 3600)


# --- Tests for clear_all_caches ---

@pytest.mark.unit
class TestClearAllCaches:
  def test_clears_files(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    must_set_cooldown(cache_dir, host, 8080, False, 3600)

    # Also create a fake credential cache file in the same dir.
    with open(os.path.join(cache_dir, "test.json"), "w") as f:
      f.write("{}")

    count = clear_all_caches(cache_dir)
    assert count >= 2  # at least the cooldown file and the cache file


# --- Tests for PID utilities ---

@pytest.mark.unit
class TestIsPidAlive:
  def test_current_process(self):
    assert is_pid_alive(os.getpid())

  def test_dead_process(self):
    assert not is_pid_alive(2147483647)

  def test_invalid_pid_zero(self):
    assert not is_pid_alive(0)

  def test_invalid_pid_negative(self):
    assert not is_pid_alive(-1)


@pytest.mark.unit
class TestWaitForPidExit:
  def test_dead_pid(self):
    exited = wait_for_pid_exit(2147483647, 1.0, 0.01)
    assert exited

  def test_live_pid(self):
    start = time.monotonic()
    exited = wait_for_pid_exit(os.getpid(), 0.05, 0.01)
    elapsed = time.monotonic() - start
    assert not exited
    assert elapsed >= 0.05


# --- Tests for get_host_cache_key ---

@pytest.mark.unit
class TestGetHostCacheKey:
  def test_with_scheme(self):
    assert get_host_cache_key("https://test.example.com") == "test.example.com"

  def test_without_scheme(self):
    assert get_host_cache_key("test.example.com") == "test.example.com"

  def test_with_trailing_slash(self):
    assert get_host_cache_key("https://test.example.com/") == "test.example.com"


# --- Tests for check_cooldown_before_listen ---

@pytest.mark.unit
class TestCheckCooldownBeforeListen:
  def test_no_cooldown(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    port, browser, timeout, result = check_cooldown_before_listen(cache_dir, host, False, 0, 3600)
    assert result is None
    assert port == 0
    assert browser is True
    assert timeout == 3600

  def test_expired_cooldown(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_duration = 3600

    write_fake_cooldown(cache_dir, host, False, 99999, 54321,
              datetime.now(timezone.utc) - timedelta(seconds=cooldown_duration + 1))

    port, browser, timeout, result = check_cooldown_before_listen(cache_dir, host, False, 0, cooldown_duration)
    assert result is None
    assert port == 0
    assert browser is True

    # Verify cooldown was cleared.
    assert read_cooldown_info(cache_dir, host, False) is None

  def test_dead_pid(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_duration = 3600

    write_fake_cooldown(cache_dir, host, False, 2147483647, 54321,
              datetime.now(timezone.utc) - timedelta(seconds=600))

    port, browser, timeout, result = check_cooldown_before_listen(cache_dir, host, False, 0, cooldown_duration)
    assert result is None
    assert port == 54321
    assert browser is False
    assert timeout < cooldown_duration

  def test_admin_independent(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_duration = 3600

    # Create non-admin cooldown with dead PID.
    write_fake_cooldown(cache_dir, host, False, 2147483647, 54321,
              datetime.now(timezone.utc) - timedelta(seconds=600))

    # Admin check should see no cooldown.
    port, browser, _, result = check_cooldown_before_listen(cache_dir, host, True, 0, cooldown_duration)
    assert result is None
    assert port == 0
    assert browser is True


# --- Tests for acquire_or_update_cooldown ---

@pytest.mark.unit
class TestAcquireOrUpdateCooldown:
  def test_fresh_start(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_duration = 3600

    result = acquire_or_update_cooldown(cache_dir, host, False, 0, 12345, True, cooldown_duration)
    assert result is None

    info = read_cooldown_info(cache_dir, host, False)
    assert info is not None
    assert info["pid"] == os.getpid()
    assert info["port"] == 12345

  def test_relay_update(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_duration = 3600

    must_set_cooldown(cache_dir, host, 8080, False, cooldown_duration)
    original_info = read_cooldown_info(cache_dir, host, False)

    # Relay path: open_browser=False.
    result = acquire_or_update_cooldown(cache_dir, host, False, 0, 9999, False, cooldown_duration)
    assert result is None

    info = read_cooldown_info(cache_dir, host, False)
    assert info["pid"] == os.getpid()
    assert info["port"] == 9999
    assert info["timestamp"] == original_info["timestamp"]


# --- Tests for read_cooldown_info ---

@pytest.mark.unit
class TestReadCooldownInfo:
  def test_returns_none_when_no_file(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    assert read_cooldown_info(cache_dir, host, False) is None

  def test_reads_existing_cooldown(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    ts = datetime.now(timezone.utc)
    write_fake_cooldown(cache_dir, host, False, 1234, 8080, ts)
    info = read_cooldown_info(cache_dir, host, False)
    assert info is not None
    assert info["pid"] == 1234
    assert info["port"] == 8080

  def test_returns_none_for_corrupt_json(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_path = _auth_cooldown_path(cache_dir, host, False)
    with open(cooldown_path, "w") as f:
      f.write("not valid json{{{")
    assert read_cooldown_info(cache_dir, host, False) is None


# --- Tests for update_cooldown ---

@pytest.mark.unit
class TestUpdateCooldown:
  def test_preserves_timestamp(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    ts = datetime.now(timezone.utc) - timedelta(seconds=300)
    write_fake_cooldown(cache_dir, host, False, 9999, 8080, ts)

    update_cooldown(cache_dir, host, False, 5555)
    info = read_cooldown_info(cache_dir, host, False)
    assert info["pid"] == os.getpid()
    assert info["port"] == 5555
    assert info["timestamp"] == ts.isoformat()

  def test_creates_new_when_none_exists(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    update_cooldown(cache_dir, host, False, 7777)
    info = read_cooldown_info(cache_dir, host, False)
    assert info is not None
    assert info["pid"] == os.getpid()
    assert info["port"] == 7777


# --- Additional tests for clear_auth_cooldown ---

@pytest.mark.unit
class TestClearAuthCooldownEdgeCases:
  def test_noop_when_no_file(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    os.makedirs(cache_dir, exist_ok=True)
    clear_auth_cooldown(cache_dir, host, False)  # should not raise


# --- Additional tests for clear_all_caches ---

@pytest.mark.unit
class TestClearAllCachesEdgeCases:
  def test_none_cache_dir(self):
    assert clear_all_caches(None) == 0

  def test_nonexistent_dir(self):
    assert clear_all_caches("/nonexistent/path/abc123") == 0

  def test_skips_subdirectories(self, tmp_path):
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir)
    with open(os.path.join(cache_dir, "file.json"), "w") as f:
      f.write("{}")
    os.makedirs(os.path.join(cache_dir, "subdir"))
    count = clear_all_caches(cache_dir)
    assert count == 1
    assert "subdir" in os.listdir(cache_dir)


# --- Additional tests for try_set_auth_cooldown ---

@pytest.mark.unit
class TestTrySetAuthCooldownExpiry:
  def test_blocked_returns_expiry(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_duration = 3600
    must_set_cooldown(cache_dir, host, 8080, False, cooldown_duration)

    ok, expiry, err = try_set_auth_cooldown(cache_dir, host, 9090, False, cooldown_duration)
    assert err is None
    assert not ok
    assert expiry is not None
    assert expiry > datetime.now(timezone.utc)

  def test_corrupt_file_treated_as_stale(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_path = _auth_cooldown_path(cache_dir, host, False)
    with open(cooldown_path, "w") as f:
      f.write("not json")

    ok, _, err = try_set_auth_cooldown(cache_dir, host, 8080, False, 3600)
    assert err is None
    assert ok, "corrupt cooldown file should be treated as stale and replaced"

  def test_missing_timestamp_returns_no_expiry(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_path = _auth_cooldown_path(cache_dir, host, False)
    with open(cooldown_path, "w") as f:
      json.dump({"pid": 12345, "port": 8080, "admin": False}, f)

    ok, expiry, err = _try_set_cooldown(cooldown_path, 9090, False, 3600, retry_on_stale=False)
    assert err is None
    assert not ok
    assert expiry is None


# --- Tests for _cached_token_result ---

@pytest.mark.unit
class TestCachedTokenResult:
  def test_no_callable_returns_none(self):
    assert _cached_token_result(None) is None

  def test_callable_returns_none_token(self):
    assert _cached_token_result(lambda: None) is None

  def test_callable_returns_token(self):
    result = _cached_token_result(lambda: "my-token-123")
    assert result == CooldownResult(token="my-token-123")


# --- Tests for _wait_for_cooldown_holder ---

@pytest.mark.unit
class TestWaitForCooldownHolder:
  def test_corrupt_timestamp_retries(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    write_fake_cooldown(cache_dir, host, False, os.getpid(), 8080,
              datetime.now(timezone.utc))
    info = read_cooldown_info(cache_dir, host, False)
    info["timestamp"] = "not-a-timestamp"

    result = _wait_for_cooldown_holder(cache_dir, host, False, 0, info, 3600)
    assert result == CooldownResult(retry=True)

  def test_expired_with_cached_token(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    ts = datetime.now(timezone.utc) - timedelta(seconds=7200)
    write_fake_cooldown(cache_dir, host, False, 2147483647, 8080, ts)
    info = {"pid": 2147483647, "port": 8080, "timestamp": ts.isoformat(), "admin": False}

    result = _wait_for_cooldown_holder(
      cache_dir, host, False, 0, info, 3600,
      get_cached_token=lambda: "cached-tok")
    assert result == CooldownResult(token="cached-tok")

  def test_expired_without_cached_token(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    ts = datetime.now(timezone.utc) - timedelta(seconds=7200)
    write_fake_cooldown(cache_dir, host, False, 2147483647, 8080, ts)
    info = {"pid": 2147483647, "port": 8080, "timestamp": ts.isoformat(), "admin": False}

    result = _wait_for_cooldown_holder(cache_dir, host, False, 0, info, 3600)
    assert result == CooldownResult(retry=True)

  def test_dead_pid_exits_with_cached_token(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    ts = datetime.now(timezone.utc) - timedelta(seconds=10)
    info = {"pid": 2147483647, "port": 8080, "timestamp": ts.isoformat(), "admin": False}

    result = _wait_for_cooldown_holder(
      cache_dir, host, False, 0, info, 3600,
      get_cached_token=lambda: "found-token")
    assert result == CooldownResult(token="found-token")

  def test_dead_pid_exits_without_cached_token(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    ts = datetime.now(timezone.utc) - timedelta(seconds=10)
    info = {"pid": 2147483647, "port": 8080, "timestamp": ts.isoformat(), "admin": False}

    result = _wait_for_cooldown_holder(cache_dir, host, False, 0, info, 3600)
    assert result == CooldownResult(retry=True)


# --- Tests for recover_relay_bind_failure ---

@pytest.mark.unit
class TestRecoverRelayBindFailure:
  def test_no_cooldown_resets(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    os.makedirs(cache_dir, exist_ok=True)
    result = recover_relay_bind_failure(cache_dir, host, False, 0, 54321, 3600)
    assert result == CooldownResult(retry=True)

  def test_dead_pid_resets(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    write_fake_cooldown(cache_dir, host, False, 2147483647, 54321,
              datetime.now(timezone.utc) - timedelta(seconds=60))

    result = recover_relay_bind_failure(cache_dir, host, False, 0, 54321, 3600)
    assert result == CooldownResult(retry=True)
    assert read_cooldown_info(cache_dir, host, False) is None


# --- Additional tests for check_cooldown_before_listen ---

@pytest.mark.unit
class TestCheckCooldownBeforeListenEdgeCases:
  def test_corrupt_timestamp_clears_and_retries(self, tmp_path):
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_path = _auth_cooldown_path(cache_dir, host, False)
    info = {"pid": os.getpid(), "port": 8080, "admin": False, "timestamp": "garbage"}
    with open(cooldown_path, "w") as f:
      json.dump(info, f)

    port, browser, timeout, result = check_cooldown_before_listen(cache_dir, host, False, 0, 3600)
    assert result is None
    assert browser is True
    assert read_cooldown_info(cache_dir, host, False) is None

  def test_expired_remaining_clears_before_pid_check(self, tmp_path):
    """When remaining <= 0 in check_cooldown_before_listen, cooldown is cleared
    and (port, True, timeout, None) is returned — PID check is never reached."""
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_duration = 3600
    ts = datetime.now(timezone.utc) - timedelta(seconds=cooldown_duration + 1)
    write_fake_cooldown(cache_dir, host, False, os.getpid(), 8080, ts)

    port, browser, timeout, result = check_cooldown_before_listen(
      cache_dir, host, False, 0, cooldown_duration,
      get_cached_token=lambda: "should-not-be-used")
    assert result is None
    assert browser is True
    assert read_cooldown_info(cache_dir, host, False) is None


# --- Additional tests for acquire_or_update_cooldown ---

@pytest.mark.unit
class TestAcquireOrUpdateCooldownEdgeCases:
  def test_blocked_by_dead_pid_retries(self, tmp_path):
    """When blocked by a dead PID's cooldown, acquire waits then returns retry."""
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_duration = 3600
    # Create cooldown held by a dead PID.
    write_fake_cooldown(cache_dir, host, False, 2147483647, 8080,
              datetime.now(timezone.utc) - timedelta(seconds=10))

    result = acquire_or_update_cooldown(cache_dir, host, False, 0, 9090, True, cooldown_duration)
    # Dead PID exits immediately → _cached_token_result(None) → retry
    assert result == CooldownResult(retry=True)

  def test_blocked_by_dead_pid_with_cached_token(self, tmp_path):
    """When blocked by a dead PID, callable provides cached token."""
    host, cache_dir = setup_test_host(tmp_path)
    cooldown_duration = 3600
    write_fake_cooldown(cache_dir, host, False, 2147483647, 8080,
              datetime.now(timezone.utc) - timedelta(seconds=10))

    result = acquire_or_update_cooldown(
      cache_dir, host, False, 0, 9090, True, cooldown_duration,
      get_cached_token=lambda: "acquire-cached")
    assert result == CooldownResult(token="acquire-cached")


# --- Tests for is_tty ---

@pytest.mark.unit
def test_is_tty_returns_bool():
  result = is_tty()
  assert isinstance(result, bool)
