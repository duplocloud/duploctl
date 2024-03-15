import pytest
import time
import random

from duplocloud.errors import DuploError
from duplocloud.client import DuploClient

duplo, _ = DuploClient.from_env()

class TestTenant:

  def setup_class(self):
    inc = random.randint(1, 100)
    self.tenant_name = f"duploctl{inc}"
    print(f"setup_method called {self.tenant_name}")

  def teardown_class(self):
    print(f"teardown_method called {self.tenant_name}")

  @pytest.mark.integration
  def test_listing_tenants(self):
    r = duplo.load("tenant")
    try:
      lot = r("list")
    except DuploError as e:
      pytest.fail(f"Failed to list tenants: {e}")
    # there is at least one tenant
    assert len(lot) > 0

  @pytest.mark.integration
  def test_finding_tenants(self):
    r = duplo.load("tenant")
    try:
      t = r("find", "default")
    except DuploError as e:
      pytest.fail(f"Failed to list tenants: {e}")
    assert t["AccountName"] == "default"

  @pytest.mark.integration
  @pytest.mark.dependency(name = "create_tenant")
  def test_creating_tenants(self):
    t = duplo.load("tenant")
    # create a random tenant and delete it from the default plan
    name = self.tenant_name
    try:
      t.create({
        "AccountName": name,
        "PlanID": "default",
        "TenantBlueprint": None
      }, wait=True)
      print(f"Tenant '{name}' created")
    except DuploError as e:
      pytest.fail(f"Failed to create tenant: {e}")

  @pytest.mark.integration
  @pytest.mark.dependency(depends=["create_tenant"])
  def test_find_delete_tenant(self):
    # now find it
    t = duplo.load("tenant")
    name = self.tenant_name
    print(f"Delete tenant '{name}'")
    try:
      nt = t("find", name)
      assert nt["AccountName"] == name
    except DuploError as e:
      pytest.fail(f"Failed to find tenant {name}: {e}")
    # now delete the tenant
    try:
      t("config", name, "-D", "delete_protection")
      t("delete", name)
    except DuploError as e:
      pytest.fail(f"Failed to delete tenant: {e}")

