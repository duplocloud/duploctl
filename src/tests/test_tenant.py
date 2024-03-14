import pytest
import time
import random

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

@pytest.mark.integration
def test_finding_tenants():
  r = duplo.load("tenant")
  try:
    t = r("find", "default")
  except DuploError as e:
    pytest.fail(f"Failed to list tenants: {e}")
  assert t["AccountName"] == "default"

@pytest.mark.integration
def test_creating_tenants():
  t = duplo.load("tenant")
  # create a random tenant and delete it from the default plan
  inc = random.randint(1, 100)
  name = f"duploctl{inc}"
  try:
    t.create({
      "AccountName": name,
      "PlanID": "default",
      "TenantBlueprint": None,
    })
  except DuploError as e:
    pytest.fail(f"Failed to create tenant: {e}")
  # for 20 seonds keep trying to find the tenant allowing to fail up to 20 seconds
  for _ in range(60):
    try:
      print(f"Trying to find tenant {name}")
      nt = t("find", name)
      print(f"Tenant {name} found")
      assert nt["AccountName"] == name
      break
    except DuploError as e:
      print(f"Failed to find tenant {name}: {e}")
      time.sleep(1)
  else:
    pytest.fail(f"Failed to find tenant {name}")
  # now delete the tenant
  try:
    t("config", name, "-D", "delete_protection")
    t("delete", name)
  except DuploError as e:
    pytest.fail(f"Failed to delete tenant: {e}")

