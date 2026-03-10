import pytest
from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError
from .conftest import get_test_data

@pytest.mark.integration
@pytest.mark.k8s
@pytest.mark.cronjob
class TestCronjobs:

  @pytest.mark.order(80)
  @pytest.mark.dependency(
    name="update_cronjob_image",
    depends=["find_tenant_resource"],
    scope='session')
  def test_update_image(self, duplo: DuploCtl):
    kind = "cronjob"
    r = duplo.load(kind)
    body = get_test_data(kind)
    name = r.name_from_body(body)
    try:
      r.update_image(name, "ubuntu:latest")
      o = r.find(name)
      assert o["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["image"] == "ubuntu:latest"
    except DuploError as e:
      pytest.fail(f"Failed to find tenant {name}: {e}")

  @pytest.mark.order(80)
  @pytest.mark.dependency(
    name="update_cronjob_schedule",
    depends=["find_tenant_resource"],
    scope='session')
  def test_update_schedule(self, duplo: DuploCtl):
    kind = "cronjob"
    r = duplo.load(kind)
    body = get_test_data(kind)
    name = r.name_from_body(body)
    try:
      r.update_schedule(name, "1 1 * * 0")
      o = r.find(name)
      assert o["spec"]["schedule"] == "1 1 * * 0"
    except DuploError as e:
      pytest.fail(f"Failed to find tenant {name}: {e}")

  @pytest.mark.order(80)
  @pytest.mark.dependency(name="is_any_host_allowed", depends=["find_tenant_resource"], scope='session')
  def test_is_any_host_allowed_true(self, duplo: DuploCtl):
    # TODO: IsAnyHostAllowed=True requires the tenant-level "Enable service on any host"
    # setting. Add a dedicated test once that setting is enabled in a target tenant,
    # or add a fixture that enables/disables it for the duration of the test.
    kind = "cronjob"
    r = duplo.load(kind)
    body = get_test_data(kind)
    name = r.name_from_body(body)
    # Delete and recreate so this test leaves the cronjob in a known state for test_is_any_host_allowed_false.
    try:
      r.delete(name)
    except DuploError:
      pass
    r.create(body)

  @pytest.mark.order(81)
  @pytest.mark.dependency(name="is_any_host_allowed", depends=["find_tenant_resource"], scope='session')
  def test_is_any_host_allowed_false(self, duplo: DuploCtl):
    kind = "cronjob"
    r = duplo.load(kind)
    body = get_test_data(kind)
    name = r.name_from_body(body)
    # Delete before recreating with annotation.
    try:
      r.delete(name)
    except DuploError:
      pass
    # Set the annotation to false
    body["metadata"]["annotations"] = {"duplocloud.net/is-any-host-allowed": "false"}
    r.create(body)
    try:
      o = r.find(name)
      # Validate the IsAnyHostAllowed is False based on the annotation
      assert o["IsAnyHostAllowed"] == False
    except DuploError as e:
      pytest.fail(f"Failed to find tenant {name}: {e}")
