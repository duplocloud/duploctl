import argparse
import pytest
from unittest.mock import MagicMock
from duplocloud.errors import DuploError
from duplocloud.argtype import MetadataAction, ALLOWED_METADATA_TYPES
from duplo_resource.tenant import DuploTenant

META_KEY = "duploctl-test-meta"

FAKE_TENANT = {"AccountName": "mytenant", "TenantId": "tid-abc"}
EXISTING_META = [
  {"Key": "existingKey", "Value": "existingVal", "Type": "text"},
]


@pytest.fixture
def tenant_resource(mocker):
  """DuploTenant with a mocked duplo client."""
  mock_client = mocker.MagicMock()
  mock_client.tenant = "mytenant"
  mock_client.tenantid = None
  mock_client.wait = False
  resource = DuploTenant(mock_client)
  return resource


# ---------------------------------------------------------------------------
# get_metadata
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_get_metadata_returns_list(tenant_resource, mocker):
  """get_metadata calls the correct endpoint and returns the JSON list."""
  mock_response = MagicMock()
  mock_response.json.return_value = EXISTING_META
  tenant_resource.duplo.get.return_value = mock_response
  mocker.patch.object(tenant_resource, "find", return_value=FAKE_TENANT)

  result = tenant_resource.get_metadata("mytenant")

  tenant_resource.duplo.get.assert_called_once_with("admin/GetTenantConfigData/tid-abc")
  assert result == EXISTING_META


@pytest.mark.unit
def test_get_metadata_empty_tenant(tenant_resource, mocker):
  """get_metadata returns an empty list when the tenant has no metadata."""
  mock_response = MagicMock()
  mock_response.json.return_value = []
  tenant_resource.duplo.get.return_value = mock_response
  mocker.patch.object(tenant_resource, "find", return_value=FAKE_TENANT)

  result = tenant_resource.get_metadata("mytenant")
  assert result == []


# ---------------------------------------------------------------------------
# set_metadata — create
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_set_metadata_creates_new_key(tenant_resource, mocker):
  """set_metadata creates a key that does not yet exist."""
  get_response = MagicMock()
  get_response.json.return_value = []
  post_response = MagicMock()
  post_response.status_code = 200
  tenant_resource.duplo.get.return_value = get_response
  tenant_resource.duplo.post.return_value = post_response
  mocker.patch.object(tenant_resource, "find", return_value=FAKE_TENANT)

  result = tenant_resource.set_metadata("mytenant", metadata=[("newKey", "text", "newVal")])

  tenant_resource.duplo.post.assert_called_once_with(
    "admin/UpdateTenantConfigData",
    {"Key": "newKey", "Value": "newVal", "Type": "text", "ComponentId": "tid-abc"},
  )
  assert "newKey" in result["changes"]["created"]
  assert result["changes"]["skipped"] == []
  assert result["changes"]["deleted"] == []


@pytest.mark.unit
def test_set_metadata_skips_existing_key(tenant_resource, mocker):
  """set_metadata skips (does not overwrite) a key that already exists."""
  get_response = MagicMock()
  get_response.json.return_value = EXISTING_META
  tenant_resource.duplo.get.return_value = get_response
  mocker.patch.object(tenant_resource, "find", return_value=FAKE_TENANT)

  result = tenant_resource.set_metadata("mytenant", metadata=[("existingKey", "text", "newVal")])

  tenant_resource.duplo.post.assert_not_called()
  assert "existingKey" in result["changes"]["skipped"]
  assert result["changes"]["created"] == []


@pytest.mark.unit
def test_set_metadata_create_api_error_raises(tenant_resource, mocker):
  """set_metadata raises DuploError when the API returns a 4xx for a create."""
  get_response = MagicMock()
  get_response.json.return_value = []
  post_response = MagicMock()
  post_response.status_code = 400
  post_response.text = "bad request"
  tenant_resource.duplo.get.return_value = get_response
  tenant_resource.duplo.post.return_value = post_response
  mocker.patch.object(tenant_resource, "find", return_value=FAKE_TENANT)

  with pytest.raises(DuploError):
    tenant_resource.set_metadata("mytenant", metadata=[("k", "text", "v")])


# ---------------------------------------------------------------------------
# set_metadata — delete
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_set_metadata_deletes_existing_key(tenant_resource, mocker):
  """set_metadata deletes a key that exists in current metadata."""
  get_response = MagicMock()
  get_response.json.return_value = EXISTING_META
  post_response = MagicMock()
  post_response.status_code = 200
  tenant_resource.duplo.get.return_value = get_response
  tenant_resource.duplo.post.return_value = post_response
  mocker.patch.object(tenant_resource, "find", return_value=FAKE_TENANT)

  result = tenant_resource.set_metadata("mytenant", deletes=["existingKey"])

  tenant_resource.duplo.post.assert_called_once_with(
    "admin/UpdateTenantConfigData",
    {"Type": "text", "Key": "existingKey", "Value": "existingVal", "ComponentId": "tid-abc", "State": "delete"},
  )
  assert "existingKey" in result["changes"]["deleted"]


@pytest.mark.unit
def test_set_metadata_delete_missing_key_raises(tenant_resource, mocker):
  """set_metadata raises DuploError when deleting a key that doesn't exist."""
  get_response = MagicMock()
  get_response.json.return_value = []
  tenant_resource.duplo.get.return_value = get_response
  mocker.patch.object(tenant_resource, "find", return_value=FAKE_TENANT)

  with pytest.raises(DuploError, match="not found"):
    tenant_resource.set_metadata("mytenant", deletes=["missingKey"])


# ---------------------------------------------------------------------------
# MetadataAction — argument validation
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_metadata_action_rejects_invalid_type():
  """MetadataAction raises ArgumentTypeError for an unrecognised type.

  argparse does not wrap ArgumentTypeError from action.__call__ into SystemExit,
  so the raw ArgumentTypeError propagates.
  """
  parser = argparse.ArgumentParser()
  parser.add_argument("--metadata", action=MetadataAction)
  with pytest.raises(argparse.ArgumentTypeError):
    parser.parse_args(["--metadata", "key", "badtype", "value"])


@pytest.mark.unit
def test_metadata_action_accepts_all_allowed_types():
  """MetadataAction accepts every type in ALLOWED_METADATA_TYPES."""
  parser = argparse.ArgumentParser()
  parser.add_argument("--metadata", action=MetadataAction)
  for mtype in ALLOWED_METADATA_TYPES:
    ns = parser.parse_args(["--metadata", "k", mtype, "v"])
    assert ns.metadata == [("k", mtype, "v")]


@pytest.mark.unit
def test_metadata_action_normalises_type_to_lowercase():
  """MetadataAction lowercases the type before storing it."""
  parser = argparse.ArgumentParser()
  parser.add_argument("--metadata", action=MetadataAction)
  ns = parser.parse_args(["--metadata", "k", "TEXT", "v"])
  assert ns.metadata[0][1] == "text"

class TestTenantMetadata:

  @pytest.mark.integration
  @pytest.mark.order(3)
  @pytest.mark.dependency(name="tenant_metadata", depends=["create_tenant"], scope='session')
  def test_tenant_metadata_lifecycle(self, duplo):
    r = duplo.load("tenant")
    name = duplo.tenant

    # 1. Read current metadata list (should not raise)
    try:
      current = r("get_metadata", name)
      assert isinstance(current, list)
    except DuploError as e:
      pytest.fail(f"Failed to list tenant metadata: {e}")

    # If key already exists from a previous run, delete it to start clean (best-effort)
    if any(m.get("Key") == META_KEY for m in current if isinstance(m, dict)):
      try:
        r("set_metadata", name, "--delete", META_KEY)
      except DuploError:
        pass

    # 2. Create metadata key
    try:
      create_result = r("set_metadata", name, "--metadata", META_KEY, "text", "v1")
      assert META_KEY in create_result["changes"]["created"]
    except DuploError as e:
      pytest.fail(f"Failed to create tenant metadata key: {e}")

    # 3. Verify created value
    try:
      after_create = r("get_metadata", name)
      found = next((m for m in after_create if isinstance(m, dict) and m.get("Key") == META_KEY), None)
      assert found is not None and found.get("Value") == "v1"
    except DuploError as e:
      pytest.fail(f"Failed to read back created metadata key: {e}")

    # 4. Attempt to re-create with different value (should skip, not change)
    try:
      second_create = r("set_metadata", name, "--metadata", META_KEY, "text", "v2")
      assert META_KEY in second_create["changes"]["skipped"]
    except DuploError as e:
      pytest.fail(f"Failed during second create (expected skip): {e}")

    # 5. Ensure value unchanged
    try:
      after_skip = r("get_metadata", name)
      found = next((m for m in after_skip if isinstance(m, dict) and m.get("Key") == META_KEY), None)
      assert found is not None and found.get("Value") == "v1"
    except DuploError as e:
      pytest.fail(f"Failed to verify skipped create behavior: {e}")

    # 6. Delete metadata key
    try:
      delete_result = r("set_metadata", name, "--delete", META_KEY)
      assert META_KEY in delete_result["changes"]["deleted"]
    except DuploError as e:
      pytest.fail(f"Failed to delete tenant metadata key: {e}")

    # 7. Confirm deletion
    try:
      final_list = r("get_metadata", name)
      assert all(m.get("Key") != META_KEY for m in final_list if isinstance(m, dict))
    except DuploError as e:
      pytest.fail(f"Failed to confirm deletion of metadata key: {e}")

  @pytest.mark.integration
  @pytest.mark.order(3)
  @pytest.mark.dependency(depends=["create_tenant"], scope='session')
  def test_invalid_type_rejected(self, duplo):
    r = duplo.load("tenant")
    name = duplo.tenant
    with pytest.raises(Exception):  # Could be ArgumentTypeError or DuploError
      r("set_metadata", name, "--metadata", "badkey", "notatype", "value")

  @pytest.mark.integration
  @pytest.mark.order(3)
  @pytest.mark.dependency(depends=["create_tenant"], scope='session')
  def test_mixed_operations(self, duplo):
    r = duplo.load("tenant")
    name = duplo.tenant
    key1 = META_KEY + "-mixed1"
    key2 = META_KEY + "-mixed2"

    # ensure clean
    try:
      r("set_metadata", name, "--delete", key1, "--delete", key2)
    except DuploError:
      pass

    # create both keys
    r("set_metadata", name, "--metadata", key1, "text", "value1")
    r("set_metadata", name, "--metadata", key2, "url", "https://example.com")

    # mixed create and delete
    result = r("set_metadata", name, "--metadata", key1, "text", "newvalue", "--delete", key2)
    assert key1 in result["changes"]["skipped"]  # key1 already exists
    assert key2 in result["changes"]["deleted"]  # key2 was deleted

    # cleanup
    r("set_metadata", name, "--delete", key1)
