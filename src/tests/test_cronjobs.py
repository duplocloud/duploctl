import pytest
from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from .conftest import get_test_data

class TestCronjobs:
  
  @pytest.mark.integration
  @pytest.mark.order(7)
  @pytest.mark.dependency(
    name="update_cronjob_image", 
    depends=["find_tenant_resource"],
    scope='session')
  def test_update_image(self, duplo: DuploClient):
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
  
  @pytest.mark.integration
  @pytest.mark.order(7)
  @pytest.mark.dependency(
    name="update_cronjob_schedule", 
    depends=["find_tenant_resource"], 
    scope='session')
  def test_update_schedule(self, duplo: DuploClient):
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
  
  

