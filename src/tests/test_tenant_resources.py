import pytest
from duplocloud.errors import DuploError
import time

resources = [
  pytest.param("cronjob",       marks=[pytest.mark.k8s, pytest.mark.cronjob]),
  pytest.param("configmap",     marks=[pytest.mark.k8s, pytest.mark.configmap]),
  # TODO: lambda requires a private ECR image accessible from the tenant account.
  # The test must dynamically build, push, and clean up the image. Skip for now.
  # pytest.param("lambda",      marks=[pytest.mark.aws, pytest.mark.lambda_]),
  # Hosts have a dedicated test file (test_hosts.py) with k8s and aws classes.
  # ASG is out of scope for the current test focus — hosts cover the node lifecycle.
  # RDS has a dedicated test file (test_rds.py) that covers the full lifecycle.
]

@pytest.mark.integration
@pytest.mark.parametrize("test_data", resources, indirect=True)
class TestTenantResources:

  @pytest.mark.order(50)
  @pytest.mark.dependency(
    name="create_tenant_resource",
    depends=["create_tenant"],
    scope='session')
  def test_creating_resource(self, test_data, duplo):
    (kind, data) = test_data
    r = duplo.load(kind)
    tenant = r.tenant["AccountName"]
    name = r.name_from_body(data)
    # If the resource already exists, pass without recreating it.
    try:
      o = r.find(name)
      if o:
        print(f"{kind} '{name}' already exists in '{tenant}'")
        return
    except DuploError:
      pass
    start_time = time.time()
    # Use the resource's own wait_timeout if set (e.g. RDS=1200s), else 45s for fast resources.
    retry_limit = getattr(r, 'wait_timeout', 45)
    print(f"Creating {kind} '{name}' in '{tenant}'")
    # For some reason you'll get a 409 a bunch of times until the tenant is actually ready.
    r.duplo.wait = True
    while True:
      try:
        r.create(body=data)
        print(f"{kind} '{name}' created in '{tenant}'")
        break
      except DuploError as e:
        elapsed_time = time.time() - start_time
        if elapsed_time > retry_limit:
          pytest.fail(f"Failed to create {kind} after {int(elapsed_time)}s: {e}")
        else:
          print(f"Attempt failed: {e}. Retrying in 5 seconds...")
          time.sleep(5)

  @pytest.mark.order(51)
  @pytest.mark.dependency(
    name="find_tenant_resource",
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
      if e.code == 404:
        print(f"{kind} '{name}' already deleted")
      else:
        pytest.fail(f"Failed to delete {kind}: {e}")

