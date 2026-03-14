import argparse

import pytest
import time
from unittest.mock import MagicMock

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError
from duplocloud.argtype import MetadataAction, ALLOWED_METADATA_TYPES
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
      print(f"\n  host:    {duplo.host}")
      print(f"  tenant:  {name}  (infra={infra_name})")
      i = t("find", name)
      if i:
        print(f"  status:  pre-existing  (plan={i.get('PlanID')}, id={i.get('TenantId')})")
        return
    except DuploError:
      pass
    print(f"  creating tenant '{name}' on infra '{infra_name}'")
    duplo.wait = True
    try:
      t.create({
        "AccountName": name,
        "PlanID": infra_name,
        "TenantBlueprint": None
      })
      print(f"  result:  tenant '{name}' created")
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


# ---------------------------------------------------------------------------
# Helpers shared by metadata unit tests
# ---------------------------------------------------------------------------

_FAKE_TENANT = {"TenantId": "tid-abc", "AccountName": "mytenant"}

_EXISTING_META = [
    {"Key": "existingKey", "Type": "text", "Value": "existingVal"},
]


def _make_tenant_resource(mocker):
  """Return a DuploTenant instance with the HTTP client fully mocked.

  The ``@Resource`` decorator assigns ``self.client = duplo.load_client()``
  in the wrapped ``__init__``.  We replace that instance attribute with a
  plain ``MagicMock`` so tests can assert on ``.get`` / ``.post`` directly.
  """
  from duplo_resource.tenant import DuploTenant
  duplo = MagicMock()
  resource = DuploTenant(duplo)
  mock_client = MagicMock()
  resource.client = mock_client
  resource._mock_client = mock_client
  mocker.patch.object(resource, "find", return_value=_FAKE_TENANT)
  return resource


# ---------------------------------------------------------------------------
# MetadataAction — argument parsing
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_metadata_action_rejects_invalid_type():
  """MetadataAction raises ArgumentTypeError for an unrecognised type."""
  parser = argparse.ArgumentParser()
  parser.add_argument("--metadata", action=MetadataAction)
  with pytest.raises(argparse.ArgumentTypeError):
    parser.parse_args(["--metadata", "key", "badtype", "value"])


@pytest.mark.unit
def test_metadata_action_accepts_all_allowed_types():
  """MetadataAction accepts every type in ALLOWED_METADATA_TYPES."""
  parser = argparse.ArgumentParser()
  parser.add_argument("--metadata", action=MetadataAction)
  for mtype in ALLOWED_METADATA_TYPES:
    ns = parser.parse_args(["--metadata", "k", mtype, "v"])
    assert ns.metadata == [("k", mtype, "v")]


@pytest.mark.unit
def test_metadata_action_normalises_type_to_lowercase():
  """MetadataAction lower-cases the type token before storing."""
  parser = argparse.ArgumentParser()
  parser.add_argument("--metadata", action=MetadataAction)
  ns = parser.parse_args(["--metadata", "k", "TEXT", "v"])
  assert ns.metadata[0][1] == "text"


@pytest.mark.unit
def test_metadata_action_is_repeatable():
  """Multiple --metadata flags accumulate as a list of tuples."""
  parser = argparse.ArgumentParser()
  parser.add_argument("--metadata", action=MetadataAction)
  ns = parser.parse_args([
      "--metadata", "k1", "text", "v1",
      "--metadata", "k2", "url", "https://example.com",
  ])
  assert len(ns.metadata) == 2
  assert ns.metadata[0] == ("k1", "text", "v1")
  assert ns.metadata[1] == ("k2", "url", "https://example.com")


# ---------------------------------------------------------------------------
# get_metadata
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_get_metadata_returns_list(mocker):
  """get_metadata calls the correct endpoint and returns the JSON list."""
  resource = _make_tenant_resource(mocker)
  resp = MagicMock()
  resp.json.return_value = _EXISTING_META
  resource._mock_client.get.return_value = resp

  result = resource.get_metadata("mytenant")

  resource._mock_client.get.assert_called_once_with(
      "admin/GetTenantConfigData/tid-abc"
  )
  assert result == _EXISTING_META


@pytest.mark.unit
def test_get_metadata_empty_returns_empty_list(mocker):
  """get_metadata returns an empty list when the tenant has no metadata."""
  resource = _make_tenant_resource(mocker)
  resp = MagicMock()
  resp.json.return_value = []
  resource._mock_client.get.return_value = resp

  result = resource.get_metadata("mytenant")

  assert result == []


# ---------------------------------------------------------------------------
# set_metadata — create
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_set_metadata_creates_new_key(mocker):
  """set_metadata POSTs a new entry when the key does not exist."""
  resource = _make_tenant_resource(mocker)
  get_resp = MagicMock()
  get_resp.json.return_value = []
  post_resp = MagicMock()
  post_resp.status_code = 200
  resource._mock_client.get.return_value = get_resp
  resource._mock_client.post.return_value = post_resp

  result = resource.set_metadata(
      "mytenant", metadata=[("newKey", "text", "newVal")]
  )

  resource._mock_client.post.assert_called_once_with(
      "admin/UpdateTenantConfigData",
      {"Key": "newKey", "Type": "text", "Value": "newVal",
       "ComponentId": "tid-abc"},
  )
  assert "newKey" in result["changes"]["created"]
  assert result["changes"]["updated"] == []
  assert result["changes"]["deleted"] == []


@pytest.mark.unit
def test_set_metadata_updates_existing_key(mocker):
  """set_metadata POSTs an update when the key already exists (upsert)."""
  resource = _make_tenant_resource(mocker)
  get_resp = MagicMock()
  get_resp.json.return_value = _EXISTING_META
  post_resp = MagicMock()
  post_resp.status_code = 200
  resource._mock_client.get.return_value = get_resp
  resource._mock_client.post.return_value = post_resp

  result = resource.set_metadata(
      "mytenant", metadata=[("existingKey", "text", "newVal")]
  )

  resource._mock_client.post.assert_called_once_with(
      "admin/UpdateTenantConfigData",
      {"Key": "existingKey", "Type": "text", "Value": "newVal",
       "ComponentId": "tid-abc"},
  )
  assert "existingKey" in result["changes"]["updated"]
  assert result["changes"]["created"] == []


@pytest.mark.unit
def test_set_metadata_api_error_raises(mocker):
  """set_metadata raises DuploError when the API returns a 4xx."""
  resource = _make_tenant_resource(mocker)
  get_resp = MagicMock()
  get_resp.json.return_value = []
  post_resp = MagicMock()
  post_resp.status_code = 400
  post_resp.text = "bad request"
  resource._mock_client.get.return_value = get_resp
  resource._mock_client.post.return_value = post_resp

  with pytest.raises(DuploError):
    resource.set_metadata("mytenant", metadata=[("k", "text", "v")])


# ---------------------------------------------------------------------------
# set_metadata — delete
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_set_metadata_deletes_existing_key(mocker):
  """set_metadata POSTs a delete payload for a key that exists."""
  resource = _make_tenant_resource(mocker)
  get_resp = MagicMock()
  get_resp.json.return_value = _EXISTING_META
  post_resp = MagicMock()
  post_resp.status_code = 200
  resource._mock_client.get.return_value = get_resp
  resource._mock_client.post.return_value = post_resp

  result = resource.set_metadata("mytenant", deletes=["existingKey"])

  resource._mock_client.post.assert_called_once_with(
      "admin/UpdateTenantConfigData",
      {
          "Key": "existingKey",
          "Type": "text",
          "Value": "existingVal",
          "ComponentId": "tid-abc",
          "State": "delete",
      },
  )
  assert "existingKey" in result["changes"]["deleted"]
  assert result["changes"]["created"] == []


@pytest.mark.unit
def test_set_metadata_delete_missing_key_raises(mocker):
  """set_metadata raises DuploError when deleting a key that does not exist."""
  resource = _make_tenant_resource(mocker)
  get_resp = MagicMock()
  get_resp.json.return_value = []
  resource._mock_client.get.return_value = get_resp

  with pytest.raises(DuploError, match="not found"):
    resource.set_metadata("mytenant", deletes=["missingKey"])


# ---------------------------------------------------------------------------
# set_metadata — mixed operations
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_set_metadata_mixed_create_and_delete(mocker):
  """set_metadata handles create and delete in a single call."""
  resource = _make_tenant_resource(mocker)
  get_resp = MagicMock()
  get_resp.json.return_value = _EXISTING_META
  post_resp = MagicMock()
  post_resp.status_code = 200
  resource._mock_client.get.return_value = get_resp
  resource._mock_client.post.return_value = post_resp

  result = resource.set_metadata(
      "mytenant",
      metadata=[("brandNewKey", "url", "https://example.com")],
      deletes=["existingKey"],
  )

  assert "brandNewKey" in result["changes"]["created"]
  assert "existingKey" in result["changes"]["deleted"]
  assert resource._mock_client.post.call_count == 2


# ---------------------------------------------------------------------------
# name_from_body
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_tenant_name_from_body_account_name():
  """name_from_body reads AccountName (the real tenant field)."""
  from duplo_resource.tenant import DuploTenant
  duplo = MagicMock()
  resource = DuploTenant(duplo)
  assert resource.name_from_body({"AccountName": "myenv"}) == "myenv"


# ---------------------------------------------------------------------------
# delete --force
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_tenant_delete_force_disables_delete_protection(mocker):
  """delete(force=True) calls set_metadata to clear delete_protection first."""
  resource = _make_tenant_resource(mocker)
  # set_metadata itself is mocked so we only verify the call signature
  mocker.patch.object(resource, "set_metadata", return_value={"changes": {}})
  post_resp = MagicMock()
  post_resp.status_code = 200
  resource._mock_client.post.return_value = post_resp

  resource.delete("mytenant", force=True)

  resource.set_metadata.assert_called_once_with(
      name="mytenant",
      metadata=[("delete_protection", "text", "false")],
  )
  resource._mock_client.post.assert_called_once_with(
      "admin/DeleteTenant/tid-abc", None
  )


@pytest.mark.unit
def test_tenant_delete_no_force_skips_metadata(mocker):
  """delete() without --force does not touch metadata."""
  resource = _make_tenant_resource(mocker)
  mocker.patch.object(resource, "set_metadata")
  post_resp = MagicMock()
  post_resp.status_code = 200
  resource._mock_client.post.return_value = post_resp

  resource.delete("mytenant")

  resource.set_metadata.assert_not_called()
  resource._mock_client.post.assert_called_once_with(
      "admin/DeleteTenant/tid-abc", None
  )
