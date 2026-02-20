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
