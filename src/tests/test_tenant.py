import random
import pytest
import time

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
  @pytest.mark.dependency(name="create_tenant", scope='session')
  @pytest.mark.order(2)
  def test_creating_tenants(self, duplo, infra_name, e2e):
    t = duplo.load("tenant")
    name = duplo.tenant
    if not name:
      inc = random.randint(1, 100)
      name = f"duploctl{inc}"
      duplo.tenant = name
    # check if the tenant already exists
    try:
      print(f"Processing tenant '{name}'")
      i = t("find", name)
      print(f"Tenant '{name}' already exists")
      if i:
        pytest.skip(f"Tenant '{name}' already exists")
    except DuploError as e:
      pass
    try:
      t.create({
        "AccountName": name,
        "PlanID": infra_name,
        "TenantBlueprint": None
      }, wait=True)
      print(f"Tenant '{name}' created")
    except DuploError as e:
      pytest.fail(f"Failed to create tenant: {e}")
    time.sleep(180)

  @pytest.mark.integration
  @pytest.mark.dependency(name="delete_tenant", depends=["create_tenant"], scope='session')
  @pytest.mark.order(998)
  def test_find_delete_tenant(self, duplo):
    # now find it
    r = duplo.load("tenant")
    name = duplo.tenant
    print(f"Delete tenant '{name}'")
    try:
      nt = r("find", name)
      # now try to find again, but using the id this time
      nt = r.find(id=nt["TenantId"])
      assert nt["AccountName"] == name
    except DuploError as e:
      pytest.fail(f"Failed to find tenant {name}: {e}")
    # now delete the tenant
    try:
      r("config", name, "-D", "delete_protection")
      r("delete", name)
    except DuploError as e:
      pytest.fail(f"Failed to delete tenant: {e}")

  @pytest.mark.integration
  def test_list_users(self, duplo):
    r = duplo.load("tenant")
    try:
      users = r("list_users", "default")
    except DuploError as e:
      pytest.fail(f"Failed to list users: {e}")
    assert isinstance(users, list)

  @pytest.mark.integration
  def test_billing(self, duplo):
    r = duplo.load("tenant")
    try:
      billing = r("billing", "default")
    except DuploError as e:
      pytest.fail(f"Failed to get billing info: {e}")
    assert isinstance(billing, dict)

  @pytest.mark.integration
  def test_region(self, duplo):
    r = duplo.load("tenant")
    try:
      region = r("region", "default")
    except DuploError as e:
      pytest.fail(f"Failed to get region: {e}")
    assert "region" in region

  @pytest.mark.integration
  def test_dns_config(self, duplo):
    r = duplo.load("tenant")
    try:
      dns = r("dns_config", "default")
    except DuploError as e:
      pytest.fail(f"Failed to get DNS config: {e}")
    assert isinstance(dns, dict)
