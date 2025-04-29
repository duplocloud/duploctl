import pytest
from duplocloud.errors import DuploError
import time

resources = [
  "hosts",
  "asg",
  "cronjob", 
  "job",
  "configmap",
  "lambda",
  "rds",
  "rds::rds-read"
]

@pytest.mark.parametrize("test_data", resources, indirect=True)
class TestTenantResources:

  @pytest.mark.integration
  @pytest.mark.order(5)
  @pytest.mark.dependency(
    name="create_tenant_resource", 
    scope='session')
  def test_creating_resource(self, test_data, duplo):
    (kind, data) = test_data
    r = duplo.load(kind)
    tenant = r.tenant["AccountName"]
    name = r.name_from_body(data)
    start_time = time.time()
    print(f"Creating {kind} '{name}' in '{tenant}'")
    # For some reason you'll get a 409 a bunch of times until the tenant is actually ready.
    while True:
      try:
        r.create(data, wait=True)
        print(f"{kind} '{name}' created in '{tenant}'")
        break
      except DuploError as e:
        elapsed_time = time.time() - start_time
        if elapsed_time > 45:
          pytest.fail(f"Failed to create {kind} after x seconds: {e}")
        else:
          print(f"Attempt failed: {e}. Retrying in 5 seconds...")
          time.sleep(5)

  @pytest.mark.integration
  @pytest.mark.order(6)
  @pytest.mark.dependency(
    name="find_tenant_resource", 
    depends=["create_tenant_resource"], 
    scope='session')
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
  
  @pytest.mark.integration
  @pytest.mark.k8s
  @pytest.mark.order(997)
  @pytest.mark.dependency(
    name="delete_tenant_resource", 
    depends=["create_tenant_resource"], 
    scope='session')
  def test_delete_resource(self, duplo, test_data):
    (kind, data) = test_data
    r = duplo.load(kind)
    name = r.name_from_body(data)
    try:
      r.delete(name)
    except DuploError as e:
      pytest.fail(f"Failed to delete {kind}: {e}")

