import pytest
import random
from duplocloud.client import DuploClient

def pytest_addoption(parser):
  parser.addoption("--e2e", action="store_true", default=False, help="run e2e tests")
  parser.addoption("--infra", action="store", default=None, help="Choose existing infra")
  parser.addoption("--tenant", action="store", default=None, help="Choose existing tenant to use")

@pytest.fixture(scope='session', autouse=True)
def infra_name(pytestconfig):
  existing = pytestconfig.getoption("infra")
  if existing:
    return existing
  inc = random.randint(1, 100)
  return f"duploctl{inc}"

@pytest.fixture(scope='session', autouse=True)
def e2e(pytestconfig):
  return pytestconfig.getoption("e2e")

@pytest.fixture(scope='session', autouse=True)
def duplo(infra_name, e2e):
  d, _ = DuploClient.from_env()
  d.disable_get_cache()
  if e2e:
    d.tenant = infra_name
  return d

@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
  """Cleanup a testing directory once we are finished."""
  def kill_infra():
    print(f"Totally cleaning up dude.")
  request.addfinalizer(kill_infra)
