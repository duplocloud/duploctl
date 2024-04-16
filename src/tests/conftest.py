import os
import pytest
import random
import yaml
import pathlib
from duplocloud.client import DuploClient

def pytest_addoption(parser):
  infra = os.getenv("DUPLO_INFRA", None)
  tenant = os.getenv("DUPLO_TENANT", None)
  parser.addoption("--e2e", action="store_true", default=False, help="run e2e tests")
  parser.addoption("--infra", action="store", default=infra, help="Choose existing infra")
  parser.addoption("--tenant", action="store", default=tenant, help="Choose existing tenant to use")

@pytest.fixture(scope='session', autouse=True)
def infra_name(pytestconfig) -> str:
  existing = pytestconfig.getoption("infra")
  if existing:
    return existing
  inc = random.randint(1, 100)
  return f"duploctl{inc}"

@pytest.fixture(scope='session', autouse=True)
def e2e(pytestconfig) -> bool:
  return pytestconfig.getoption("e2e")

@pytest.fixture(scope='session', autouse=True)
def duplo(infra_name: str, e2e: bool) -> DuploClient:
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

@pytest.fixture
def test_data(request) -> tuple[str, dict]:
  """Fixture to load test data from a yaml file.
  
  Splits like this: kind::file
  example with a data file named big_host with host data would be: host::big_host
  """
  test_id = request.param.split("::")
  kind = test_id[0]
  file = test_id[-1]
  print(f"Loading test data for {kind} from {file}")
  data = get_test_data(file)
  return (kind, data)

def get_test_data(name) -> dict:
  # get the directory this file is in
  dir = pathlib.Path(__file__).parent.resolve()
  f = f"{dir}/data/{name}.yaml"
  with open(f, 'r') as stream:
    return yaml.safe_load(stream)
