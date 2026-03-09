import pytest
import random

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploFailedResource
from .conftest import get_test_data, _INFRA_DATA

@pytest.mark.integration
@pytest.mark.lifecycle
@pytest.mark.k8s
@pytest.mark.aws
@pytest.mark.ecs
class TestInfra:

  # def setup_class(self):
  #   inc = random.randint(1, 100)
  #   self.infra_name = f"duploctl{inc}"

  @pytest.mark.order(2)
  def test_listing_infrastructures(self, duplo: DuploCtl):
    r = duplo.load("infrastructure")
    try:
      lot = r("list")
    except DuploError as e:
      pytest.fail(f"Failed to list infrastructures: {e}")

  @pytest.mark.order(2)
  def test_finding_infra(self, duplo: DuploCtl):
    r = duplo.load("tenant")
    try:
      t = r("find", "default")
    except DuploError as e:
      pytest.fail(f"Failed to find default infra: {e}")
    assert t["AccountName"] == "default"

  @pytest.mark.dependency(name = "create_infra", scope='session')
  @pytest.mark.order(1)
  def test_creating_infrastructures(self, duplo: DuploCtl, infra_name: str, infra_type: str, region: str):
    r = duplo.load("infrastructure")
    try:
      existing = r.find(infra_name)
      if existing:
        if region and existing.get("Region") != region:
          print(
            f"WARNING: --region {region!r} ignored — "
            f"infrastructure '{infra_name}' already exists in {existing.get('Region')!r}"
          )
        print(f"Infrastructure '{infra_name}' already exists")
        return
    except DuploError:
      pass
    body = get_test_data(_INFRA_DATA[infra_type])
    body["Name"] = infra_name
    taken = {i.get("Vnet", {}).get("AddressPrefix", "") for i in r.list()}
    for _ in range(50):
      cidr = f"11.{random.randint(10, 250)}.0.0/16"
      if cidr not in taken:
        break
    body["Vnet"]["AddressPrefix"] = cidr
    if region:
      body["Region"] = region
    duplo.wait = True
    try:
      r.create(body)
    except DuploFailedResource as e:
      pytest.fail(f"Infrastructure is in a failed state: {e}")
    except DuploError as e:
      pytest.fail(f"Failed to create infrastructure: {e}")
    
  @pytest.mark.dependency(depends=["create_infra"], scope='session')
  @pytest.mark.order(999)
  def test_find_delete_infra(self, duplo: DuploCtl, infra_name: str, owns_infra: bool):
    if not owns_infra:
      pytest.skip(f"Infrastructure '{infra_name}' was pre-existing — not destroying")
    r = duplo.load("infrastructure")
    name = infra_name
    print(f"Deleting infra '{name}'")
    try:
      i = r.find(name)
      assert i["Name"] == name
    except DuploError as e:
      pytest.fail(f"Failed to find infrastructure {name}: {e}")
    try:
      r("delete", name)
    except DuploError as e:
      pytest.fail(f"Failed to delete infrastructure: {e}")
