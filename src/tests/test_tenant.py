import pytest

from duplocloud.errors import DuploError

class TestTenant:

  @pytest.mark.integration
  def test_listing_tenants(self, duplo):
    r = duplo.load("tenant")
    try:
      lot = r("list")
    except DuploError as e:
      pytest.fail(f"Failed to list tenants: {e}")
    # there is at least one tenant
    assert len(lot) > 0

  @pytest.mark.integration
  def test_finding_tenants(self, duplo):
    r = duplo.load("tenant")
    try:
      t = r("find", "default")
    except DuploError as e:
      pytest.fail(f"Failed to list tenants: {e}")
    assert t["AccountName"] == "default"

  @pytest.mark.integration
  @pytest.mark.dependency(name="create_tenant", depends=["create_infra"], scope='session')
  @pytest.mark.order(2)
  def test_creating_tenants(self, duplo, infra_name):
    t = duplo.load("tenant")
    # create a random tenant and delete it from the default plan
    # name = self.tenant_name
    name = infra_name
    try:
      t.create({
        "AccountName": name,
        "PlanID": infra_name,
        "TenantBlueprint": None
      }, wait=True)
      print(f"Tenant '{name}' created")
    except DuploError as e:
      pytest.fail(f"Failed to create tenant: {e}")

  @pytest.mark.integration
  @pytest.mark.dependency(name="delete_tenant", depends=["create_tenant"], scope='session')
  @pytest.mark.order(3)
  def test_find_delete_tenant(self, duplo, infra_name):
    # now find it
    t = duplo.load("tenant")
    # name = self.tenant_name
    name = infra_name
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

