import pytest
import random

@pytest.fixture(scope='session', autouse=True)
def infra_name(request):
  inc = random.randint(1, 100)
  return f"duploctl{inc}"
