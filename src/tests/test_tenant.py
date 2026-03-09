import pytest
import time

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError
from tests.conftest import get_test_data

@pytest.mark.integration
@pytest.mark.lifecycle
@pytest.mark.k8s
@pytest.mark.aws
@pytest.mark.ecs
class TestTenant:

  @pytest.mark.order(11)
  def test_listing_tenants(self, duplo):
    r = duplo.load("tenant")
    try:
      lot = r("list")
    except DuploError as e:
      pytest.fail(f"Failed to list tenants: {e}")
    # there is at least one tenant
    assert len(lot) > 0

  @pytest.mark.order(11)
  def test_finding_tenants(self, duplo):
    r = duplo.load("tenant")
    try:
      t = r("find", "default")
    except DuploError as e:
      pytest.fail(f"Failed to list tenants: {e}")
    assert t["AccountName"] == "default"

  @pytest.mark.dependency(name="create_tenant", scope='session')
  @pytest.mark.order(10)
  def test_creating_tenants(self, duplo, infra_name, tenant_name):
    t = duplo.load("tenant")
    name = tenant_name
    # check if the tenant already exists — pass without creating if it does
    try:
      print(f"Processing tenant '{name}'")
      i = t("find", name)
      if i:
        print(f"Tenant '{name}' already exists")
        return
    except DuploError:
      pass
    duplo.wait = True
    try:
      t.create({
        "AccountName": name,
        "PlanID": infra_name,
        "TenantBlueprint": None
      })
      print(f"Tenant '{name}' created")
    except DuploError as e:
      pytest.fail(f"Failed to create tenant: {e}")
    time.sleep(180)

  @pytest.mark.dependency(name="delete_tenant", depends=["create_tenant"], scope='session')
  @pytest.mark.order(998)
  def test_find_delete_tenant(self, duplo, tenant_name, owns_tenant: bool):
    if not owns_tenant:
      pytest.skip(f"Tenant '{tenant_name}' was pre-existing — not destroying")
    # now find it
    r = duplo.load("tenant")
    name = tenant_name
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

  @pytest.mark.order(12)
  def test_list_users(self, duplo):
    r = duplo.load("tenant")
    try:
      users = r("list_users", "default")
    except DuploError as e:
      pytest.fail(f"Failed to list users: {e}")
    assert isinstance(users, list)

  @pytest.mark.order(12)
  def test_billing(self, duplo):
    r = duplo.load("tenant")
    try:
      billing = r("billing", "default")
    except DuploError as e:
      pytest.fail(f"Failed to get billing info: {e}")
    assert isinstance(billing, dict)

  @pytest.mark.order(12)
  def test_region(self, duplo):
    r = duplo.load("tenant")
    try:
      region = r("region", "default")
    except DuploError as e:
      pytest.fail(f"Failed to get region: {e}")
    assert "region" in region

  @pytest.mark.order(12)
  def test_dns_config(self, duplo):
    r = duplo.load("tenant")
    try:
      dns = r("dns_config", "default")
    except DuploError as e:
      pytest.fail(f"Failed to get DNS config: {e}")
    assert isinstance(dns, dict)


@pytest.mark.unit
def test_tenant_create_model_annotation():
  """create command on DuploTenant is annotated with the AddTenantRequest model"""
  from duplocloud.commander import get_command_schema
  from duplo_resource.tenant import DuploTenant
  cmd = get_command_schema(DuploTenant, "create")
  assert cmd["model"] == "AddTenantRequest"


@pytest.mark.unit
def test_validate_tenant_yaml():
  """validate_model accepts tenant.yaml test data against AddTenantRequest"""
  duplo = DuploCtl(host="https://example.duplocloud.net")
  model_cls = duplo.load_model("AddTenantRequest")
  data = get_test_data("tenant")
  result = duplo.validate_model(model_cls, data)
  assert isinstance(result, dict)
  assert result["AccountName"] == data["AccountName"]
  assert result["PlanID"] == data["PlanID"]
