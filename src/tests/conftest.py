import pytest
import random
from duplocloud.client import DuploClient

@pytest.fixture(scope='session', autouse=True)
def infra_name(request):
  inc = random.randint(1, 100)
  return f"duploctl{inc}"

@pytest.fixture(scope='session', autouse=True)
def duplo(request):
  duplo, _ = DuploClient.from_env()
  return duplo

@pytest.fixture(scope="session", autouse=True)
def cleanup(request, duplo, infra_name):
    """Cleanup a testing directory once we are finished."""
    def kill_infra():
      print(f"Deleting infra '{infra_name}'")
      # r = duplo.load("infrastructure")
      # r("delete", infra_name)
      print(f"marks are {request}")
    request.addfinalizer(kill_infra)

