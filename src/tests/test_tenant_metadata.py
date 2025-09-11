import pytest
from duplocloud.errors import DuploError

META_KEY = "duploctl-test-meta"

class TestTenantMetadata:

  @pytest.mark.integration
  @pytest.mark.order(3)
  @pytest.mark.dependency(name="tenant_metadata", depends=["create_tenant"], scope='session')
  def test_tenant_metadata_lifecycle(self, duplo):
    r = duplo.load("tenant")
    name = duplo.tenant

    # 1. Read current metadata list (should not raise)
    try:
      current = r("metadata", name)
      assert isinstance(current, list)
    except DuploError as e:
      pytest.fail(f"Failed to list tenant metadata: {e}")

    # If key already exists from a previous run, delete it to start clean (best-effort)
    if any(m.get("Key") == META_KEY for m in current if isinstance(m, dict)):
      try:
        r("metadata", name, "--delete", META_KEY)
      except DuploError:
        pass

    # 2. Create metadata key
    try:
      create_result = r("metadata", name, "--set", META_KEY, "text", "v1")
      assert META_KEY in create_result["changes"]["created"]
    except DuploError as e:
      pytest.fail(f"Failed to create tenant metadata key: {e}")

    # 3. Verify created value
    try:
      after_create = r("metadata", name)
      found = next((m for m in after_create if isinstance(m, dict) and m.get("Key") == META_KEY), None)
      assert found is not None and found.get("Value") == "v1"
    except DuploError as e:
      pytest.fail(f"Failed to read back created metadata key: {e}")

    # 4. Attempt to re-create with different value (should skip, not change)
    try:
      second_create = r("metadata", name, "--set", META_KEY, "text", "v2")
      assert META_KEY in second_create["changes"]["skipped"]
    except DuploError as e:
      pytest.fail(f"Failed during second create (expected skip): {e}")

    # 5. Ensure value unchanged
    try:
      after_skip = r("metadata", name)
      found = next((m for m in after_skip if isinstance(m, dict) and m.get("Key") == META_KEY), None)
      assert found is not None and found.get("Value") == "v1"
    except DuploError as e:
      pytest.fail(f"Failed to verify skipped create behavior: {e}")

    # 6. Delete metadata key
    try:
      delete_result = r("metadata", name, "--delete", META_KEY)
      assert META_KEY in delete_result["changes"]["deleted"]
    except DuploError as e:
      pytest.fail(f"Failed to delete tenant metadata key: {e}")

    # 7. Confirm deletion
    try:
      final_list = r("metadata", name)
      assert all(m.get("Key") != META_KEY for m in final_list if isinstance(m, dict))
    except DuploError as e:
      pytest.fail(f"Failed to confirm deletion of metadata key: {e}")

  @pytest.mark.integration
  @pytest.mark.order(3)
  @pytest.mark.dependency(depends=["create_tenant"], scope='session')
  def test_invalid_type_rejected(self, duplo):
    """Invalid metadata types should be rejected by argparse layer.

    We expect a SystemExit (argparse behavior) when providing an unsupported type.
    """
    r = duplo.load("tenant")
    name = duplo.tenant
    with pytest.raises(SystemExit):
      r("metadata", name, "--set", "badkey", "notatype", "value")

  @pytest.mark.integration
  @pytest.mark.order(3)
  @pytest.mark.dependency(depends=["create_tenant"], scope='session')
  def test_get_single_key(self, duplo):
    r = duplo.load("tenant")
    name = duplo.tenant
    key = META_KEY + "-get"
    # ensure clean
    try:
      r("metadata", name, "--delete", key)
    except DuploError:
      pass
    # create
    r("metadata", name, "--set", key, "text", "value123")
    # get full object
    obj = r("metadata", name, "--get", key)
    assert isinstance(obj, dict) and obj.get("Key") == key and obj.get("Value") == "value123"
    # get value only
    val = r("metadata", name, "--get-value", key)
    assert val == "value123"
    # not found (object)
    with pytest.raises(DuploError):
      r("metadata", name, "--get", "does-not-exist-xyz")
    # not found (value)
    with pytest.raises(DuploError):
      r("metadata", name, "--get-value", "does-not-exist-xyz")
    # invalid combination get + get-value
    with pytest.raises(DuploError):
      r("metadata", name, "--get", key, "--get-value", key)
    # invalid combination with mutation
    with pytest.raises(DuploError):
      r("metadata", name, "--get-value", key, "--delete", key)
    # cleanup
    r("metadata", name, "--delete", key)
