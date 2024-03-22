import pytest
import random
from duplocloud.client import DuploClient

def pytest_addoption(parser):
  parser.addoption("--tenant", action="store", default=None)

@pytest.fixture(scope='session', autouse=True)
def infra_name(request):
  inc = random.randint(1, 100)
  return f"duploctl{inc}"

@pytest.fixture(scope="session")
def tenant_name(pytestconfig, infra_name):
    tenant = pytestconfig.getoption("tenant")
    if tenant is None:
        tenant = infra_name
    return tenant

@pytest.fixture(scope='session', autouse=True)
def duplo(request, tenant_name):
  d, _ = DuploClient.from_env()
  d.disable_get_cache()
  return d

@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
  """Cleanup a testing directory once we are finished."""
  def kill_infra():
    print(f"Totally cleaning up dude.")
  request.addfinalizer(kill_infra)
