import os
import stat

import pytest
import yaml
from unittest.mock import MagicMock

from duplocloud.config import DuploConfig, VALID_CONTEXT_KEYS
from duplocloud.errors import DuploError, DuploNotFound
from duplo_resource.config import DuploConfigResource

CONFIG_FIXTURE = {
  "current-context": "primary",
  "config": {"browser": "firefox"},
  "contexts": [
    {
      "name": "primary",
      "host": "https://primary.duplocloud.net",
      "token": "secret-token",
      "helpdesk_token": "dahp_secret",
      "tenant": "dev01",
      "custom_key": "kept",
    },
    {
      "name": "other",
      "host": "https://other.duplocloud.net",
    },
  ],
}


def write_fixture(tmp_path):
  """Write the two-context fixture config file and return its path."""
  path = str(tmp_path / "config")
  with open(path, "w") as f:
    yaml.safe_dump(CONFIG_FIXTURE, f, sort_keys=False)
  return path


def make_resource(tmp_path, ctx=None, missing=False):
  """Build a config resource around a MagicMock duplo and a real store."""
  path = str(tmp_path / "config") if missing else write_fixture(tmp_path)
  mock_duplo = MagicMock()
  mock_duplo.config_store = DuploConfig(path)
  mock_duplo._context = ctx
  mock_duplo.validate = False
  return DuploConfigResource(mock_duplo)


@pytest.mark.unit
class TestConfigResource:
  def test_view_redacts_tokens(self, tmp_path):
    """Test view redacts tokens without touching the cached data."""
    resource = make_resource(tmp_path)
    doc = resource.view()
    assert doc["contexts"][0]["token"] == "REDACTED"
    assert doc["contexts"][0]["helpdesk_token"] == "REDACTED"
    assert doc["config"] == {"browser": "firefox"}
    # the cached document must keep the real values
    assert resource.store.data["contexts"][0]["token"] == "secret-token"

  def test_missing_file_errors(self, tmp_path):
    """Test view/get/unset/use raise a 500 when the file is missing."""
    resource = make_resource(tmp_path, missing=True)
    for call in (lambda: resource.view(),
                 lambda: resource.get("host"),
                 lambda: resource.unset("host"),
                 lambda: resource.use("primary")):
      with pytest.raises(DuploError, match="Duplo config not found"):
        call()

  def test_get_current_and_ctx_override(self, tmp_path):
    """Test get reads from current-context and honors --ctx."""
    resource = make_resource(tmp_path)
    assert resource.get("host") == {
      "context": "primary", "host": "https://primary.duplocloud.net"}
    other = make_resource(tmp_path, ctx="other")
    assert other.get("host") == {
      "context": "other", "host": "https://other.duplocloud.net"}

  def test_invalid_keys_rejected(self, tmp_path):
    """Test get/set/unset reject keys outside the allowlist."""
    resource = make_resource(tmp_path)
    before = open(resource.store.path).read()
    for call in (lambda: resource.get("bogus"),
                 lambda: resource.set("bogus", "x"),
                 lambda: resource.unset("name")):
      with pytest.raises(DuploError, match="Valid keys:"):
        call()
    assert open(resource.store.path).read() == before

  def test_set_writes_and_preserves_unknown_keys(self, tmp_path):
    """Test set rewrites the file preserving unrelated content."""
    resource = make_resource(tmp_path)
    result = resource.set("workspace", "my-ws")
    assert result == {"message": "set workspace in context 'primary'"}
    with open(resource.store.path) as f:
      doc = yaml.safe_load(f)
    primary = doc["contexts"][0]
    assert primary["workspace"] == "my-ws"
    assert primary["custom_key"] == "kept"
    assert doc["config"] == {"browser": "firefox"}
    assert doc["contexts"][1] == CONFIG_FIXTURE["contexts"][1]
    leftovers = [e for e in os.listdir(str(tmp_path)) if ".tmp." in e]
    assert leftovers == []

  def test_set_boolean_coercion(self, tmp_path):
    """Test boolean keys coerce true/false and reject other values."""
    resource = make_resource(tmp_path)
    resource.set("interactive", "True")
    with open(resource.store.path) as f:
      doc = yaml.safe_load(f)
    assert doc["contexts"][0]["interactive"] is True
    with pytest.raises(DuploError, match="use true or false"):
      resource.set("interactive", "maybe")

  def test_set_upserts_new_context(self, tmp_path):
    """Test set with --ctx creates a missing context in the file."""
    resource = make_resource(tmp_path, ctx="newctx")
    resource.set("host", "https://new.duplocloud.net")
    with open(resource.store.path) as f:
      doc = yaml.safe_load(f)
    names = [c["name"] for c in doc["contexts"]]
    assert "newctx" in names
    # current-context was already set, so it must not change
    assert doc["current-context"] == "primary"

  def test_set_scaffolds_missing_file(self, tmp_path):
    """Test set with --ctx scaffolds a brand new config file."""
    resource = make_resource(tmp_path, ctx="newctx", missing=True)
    resource.set("host", "https://new.duplocloud.net")
    with open(resource.store.path) as f:
      doc = yaml.safe_load(f)
    assert doc["current-context"] == "newctx"
    assert doc["contexts"] == [
      {"name": "newctx", "host": "https://new.duplocloud.net"}]

  def test_set_missing_file_without_ctx_errors(self, tmp_path):
    """Test set on a missing file without --ctx asks for a context."""
    resource = make_resource(tmp_path, missing=True)
    with pytest.raises(DuploError, match="pass --ctx"):
      resource.set("host", "https://x")
    assert not os.path.exists(resource.store.path)

  def test_unset_removes_key_and_absent_is_noop(self, tmp_path):
    """Test unset removes a set key and succeeds on an absent one."""
    resource = make_resource(tmp_path)
    result = resource.unset("tenant")
    assert result == {"message": "unset tenant in context 'primary'"}
    with open(resource.store.path) as f:
      doc = yaml.safe_load(f)
    assert "tenant" not in doc["contexts"][0]
    assert resource.unset("workspace") == {
      "message": "unset workspace in context 'primary'"}

  def test_use_switches_context(self, tmp_path):
    """Test use rewrites current-context and validates the name."""
    resource = make_resource(tmp_path)
    assert resource.use("other") == {
      "message": "switched to context 'other'"}
    with open(resource.store.path) as f:
      assert yaml.safe_load(f)["current-context"] == "other"
    before = open(resource.store.path).read()
    with pytest.raises(DuploError, match="not found in config"):
      resource.use("nope")
    assert open(resource.store.path).read() == before
    with pytest.raises(DuploError, match="context name is required"):
      resource.use()

  def test_cli_dispatch(self, tmp_path):
    """Test commands run through resource(cmd) dispatch (DUPLO-41877)."""
    resource = make_resource(tmp_path)
    result = resource("set", "workspace", "my-ws")
    assert result == {"message": "set workspace in context 'primary'"}
    assert resource("use", "other") == {
      "message": "switched to context 'other'"}

  def test_store_stays_coherent_after_write(self, tmp_path):
    """Test the shared store reflects writes without a re-read."""
    resource = make_resource(tmp_path)
    resource.set("workspace", "my-ws")
    assert resource.duplo.config_store.data[
      "contexts"][0]["workspace"] == "my-ws"


@pytest.mark.unit
class TestDuploConfig:
  def test_missing_file_errors(self, tmp_path):
    """Test reading a missing config file raises a 500."""
    store = DuploConfig(str(tmp_path / "config"))
    with pytest.raises(DuploError, match="Duplo config not found"):
      store.data

  def test_get_context_lookup_and_errors(self, tmp_path):
    """Test context lookup by name plus both error messages."""
    store = DuploConfig(write_fixture(tmp_path))
    assert store.get_context()["name"] == "primary"
    assert store.get_context("other")["name"] == "other"
    with pytest.raises(DuploError, match="Portal 'nope' not found"):
      store.get_context("nope")
    empty = DuploConfig(str(tmp_path / "empty"))
    with open(empty.path, "w") as f:
      yaml.safe_dump({"contexts": []}, f)
    with pytest.raises(DuploError, match="context not set"):
      empty.get_context()

  def test_missing_contexts_key_is_not_a_keyerror(self, tmp_path):
    """Test a config with no contexts key raises a DuploError."""
    store = DuploConfig(str(tmp_path / "config"))
    with open(store.path, "w") as f:
      yaml.safe_dump({"current-context": "primary"}, f)
    with pytest.raises(DuploError, match="Portal 'primary' not found"):
      store.get_context()

  def test_save_is_atomic_and_private(self, tmp_path):
    """Test save creates parent dirs, chmods 0o600, leaves no tmp."""
    path = str(tmp_path / "deep" / "dir" / "config")
    store = DuploConfig(path)
    store.save({"current-context": None, "contexts": []})
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600
    leftovers = [e for e in os.listdir(os.path.dirname(path))
                 if ".tmp." in e]
    assert leftovers == []

  def test_empty_file_loads_as_scaffold(self, tmp_path):
    """Test an empty config file loads as a scaffold, not None."""
    store = DuploConfig(str(tmp_path / "config"))
    with open(store.path, "w") as f:
      f.write("\n")
    assert store.data == {"current-context": None, "contexts": []}
    with pytest.raises(DuploError, match="context not set"):
      store.get_context()

  def test_failed_write_leaves_no_temp_file(self, tmp_path,
                                            monkeypatch):
    """Test a dump failure cleans up its temp file.

    A failed write must never orphan a temp file holding tokens,
    regardless of the process umask.
    """
    import duplocloud.config as config_module
    path = str(tmp_path / "config")
    store = DuploConfig(path)
    monkeypatch.setattr(
      config_module.yaml, "safe_dump",
      MagicMock(side_effect=RuntimeError("boom")))
    old_umask = os.umask(0o022)
    try:
      with pytest.raises(RuntimeError):
        store.save({"current-context": None, "contexts": []})
    finally:
      os.umask(old_umask)
    assert [e for e in os.listdir(str(tmp_path)) if ".tmp." in e] == []

  def test_write_refuses_precreated_temp_path(self, tmp_path):
    """Test the exclusive create fails on a pre-created temp path.

    A file or symlink squatting on the predictable temp name must
    fail the write instead of being followed or overwritten.
    """
    path = str(tmp_path / "config")
    store = DuploConfig(path)
    tmp = f"{path}.tmp.{os.getpid()}"
    victim = str(tmp_path / "victim")
    with open(victim, "w") as f:
      f.write("untouched")
    os.symlink(victim, tmp)
    with pytest.raises(FileExistsError):
      store.save({"current-context": None, "contexts": []})
    assert open(victim).read() == "untouched"
    assert not os.path.exists(path)

  def test_non_mapping_config_errors(self, tmp_path):
    """Test list/scalar roots and malformed YAML raise DuploError."""
    store = DuploConfig(str(tmp_path / "config"))
    with open(store.path, "w") as f:
      f.write("- just\n- a\n- list\n")
    with pytest.raises(DuploError, match="must be a YAML mapping"):
      store.data
    broken = DuploConfig(str(tmp_path / "broken"))
    with open(broken.path, "w") as f:
      f.write("contexts: [unclosed\n")
    with pytest.raises(DuploError, match="Invalid YAML"):
      broken.data

  def test_failed_save_leaves_cache_untouched(self, tmp_path,
                                              monkeypatch):
    """Test a failed write never leaves phantom values in the cache."""
    import duplocloud.config as config_module
    store = DuploConfig(write_fixture(tmp_path))
    assert store.get_context()["tenant"] == "dev01"
    monkeypatch.setattr(
      config_module, "_atomic_write_yaml",
      MagicMock(side_effect=OSError("disk full")))
    for call in (lambda: store.set_key("tenant", "phantom"),
                 lambda: store.unset_key("tenant"),
                 lambda: store.set_current_context("other")):
      with pytest.raises(OSError):
        call()
    assert store.get_context()["tenant"] == "dev01"
    assert store.data["current-context"] == "primary"

  def test_valid_keys_include_helpdesk(self):
    """Test the allowlist carries the helpdesk context keys."""
    for key in ("environment", "resource_group",
                "helpdesk_host", "helpdesk_token"):
      assert key in VALID_CONTEXT_KEYS


@pytest.mark.unit
class TestWorkspaceUse:
  def test_use_persists_canonical_name(self):
    """Test workspace use validates then delegates to config set."""
    from duplo_resource.workspace import DuploWorkspace
    ws = DuploWorkspace.__new__(DuploWorkspace)
    ws.duplo = MagicMock()
    ws.find = MagicMock(return_value={"name": "Canonical"})
    config = MagicMock()
    ws.duplo.load.return_value = config
    config.set.return_value = {
      "message": "set workspace in context 'primary'"}
    result = DuploWorkspace.use(ws, "canonical")
    ws.find.assert_called_once_with("canonical")
    ws.duplo.load.assert_called_once_with("config")
    config.set.assert_called_once_with("workspace", "Canonical")
    assert result == {"message": "set workspace in context 'primary'"}

  def test_use_requires_name_and_propagates_not_found(self):
    """Test missing name errors and find failures skip config."""
    from duplo_resource.workspace import DuploWorkspace
    ws = DuploWorkspace.__new__(DuploWorkspace)
    ws.duplo = MagicMock()
    with pytest.raises(DuploError, match="workspace name is required"):
      DuploWorkspace.use(ws)
    ws.find = MagicMock(side_effect=DuploNotFound("nope", "workspace"))
    with pytest.raises(DuploNotFound):
      DuploWorkspace.use(ws, "nope")
    ws.duplo.load.assert_not_called()
