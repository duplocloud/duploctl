import pytest

from duplocloud.errors import DuploError
from duplocloud.client import DuploClient

duplo, _ = DuploClient.from_env()

@pytest.mark.integration
def test_listing_tenants():
  r = duplo.load("tenant")
  try:
    lot = r("list")
  except DuploError as e:
    pytest.fail(f"Failed to list tenants: {e}")
  # there is at least one tenant
  assert len(lot) > 1


