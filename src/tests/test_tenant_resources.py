import pytest
from duplocloud.errors import DuploError
from .helpers import get_test_data
import time

@pytest.mark.parametrize("test_data", ["cronjob", "job"], indirect=True)
class TestTenantResources:

  @pytest.mark.integration
  @pytest.mark.order(5)
  @pytest.mark.dependency(name="create_tenant_resource")
  def test_creating_resource(self, test_data, duplo):
    (kind, data) = test_data
    r = duplo.load(kind)
    name = r.name_from_body(data)
    start_time = time.time()
    print(f"Creating {kind} '{name}' in '{duplo.tenant}'")
    # For some reason you'll get a 409 a bunch of times until the tenant is actually ready.
    while True:
      try:
        r.create(data, wait=True)
        print(f"{kind} '{name}' created in '{duplo.tenant}'")
        break
      except DuploError as e:
        elapsed_time = time.time() - start_time
        if elapsed_time > 45:
          pytest.fail(f"Failed to create {kind} after 20 seconds: {e}")
        else:
          print(f"Attempt failed: {e}. Retrying in 5 seconds...")
          time.sleep(5)


  @pytest.mark.integration
  @pytest.mark.order(6)
  @pytest.mark.dependency(name="find_tenant_resource", depends=["create_tenant_resource"])
  def test_find_resource(self, duplo, test_data):
    (kind, data) = test_data
    r = duplo.load(kind)
    name = r.name_from_body(data)
    try:
      o = r.find(name)
      assert r.name_from_body(o) == name
      print(f"Found {kind} '{name}'")
    except DuploError as e:
      pytest.fail(f"Failed to find {kind} {name}: {e}")
  
  # @pytest.mark.integration
  # @pytest.mark.order(7)
  # @pytest.mark.dependency(name="update_cronjob_image", depends=["find_cronjob"])
  # def test_update_image(self, duplo):
  #   name = "duploctl"
  #   r = duplo.load("cronjob")
  #   try:
  #     r.update_image(name, "ubuntu:latest")
  #     o = r.find(name)
  #     assert o["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["image"] == "ubuntu:latest"
  #   except DuploError as e:
  #     pytest.fail(f"Failed to find tenant {name}: {e}")
  
  # @pytest.mark.integration
  # @pytest.mark.dependency(name="update_cronjob_schedule", depends=["create_cronjob"], scope='session')
  # @pytest.mark.order(7)
  # def test_update_schedule(self, duplo):
  #   name = "duploctl"
  #   r = duplo.load("cronjob")
  #   try:
  #     r.update_schedule(name, "1 1 * * 0")
  #     o = r.find(name)
  #     assert o["spec"]["schedule"] == "1 1 * * 0"
  #   except DuploError as e:
  #     pytest.fail(f"Failed to find tenant {name}: {e}")
  
  @pytest.mark.integration
  @pytest.mark.k8s
  @pytest.mark.dependency(name="delete_tenant_resource", depends=["create_tenant_resource"])
  @pytest.mark.order(8)
  def test_delete_resource(self, duplo, test_data):
    (kind, data) = test_data
    r = duplo.load(kind)
    name = r.name_from_body(data)
    try:
      r.delete(name)
    except DuploError as e:
      pytest.fail(f"Failed to delete {kind}: {e}")

