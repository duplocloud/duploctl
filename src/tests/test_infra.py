import math
import pytest
import random

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploFailedResource

@pytest.mark.k8s
@pytest.mark.aws
@pytest.mark.ecs
class TestInfra:

  # def setup_class(self):
  #   inc = random.randint(1, 100)
  #   self.infra_name = f"duploctl{inc}"

  @pytest.mark.integration
  @pytest.mark.order(2)
  def test_listing_infrastructures(self, duplo: DuploCtl):
    r = duplo.load("infrastructure")
    try:
      lot = r("list")
    except DuploError as e:
      pytest.fail(f"Failed to list infrastructures: {e}")

  @pytest.mark.integration
  @pytest.mark.order(2)
  def test_finding_infra(self, duplo: DuploCtl):
    r = duplo.load("tenant")
    try:
      t = r("find", "default")
    except DuploError as e:
      pytest.fail(f"Failed to find default infra: {e}")
    assert t["AccountName"] == "default"

  @pytest.mark.integration
  @pytest.mark.dependency(name = "create_infra", scope='session')
  @pytest.mark.order(1)
  def test_creating_infrastructures(self, duplo: DuploCtl, infra_name: str):
    r = duplo.load("infrastructure")
    vnum = math.ceil(random.randint(1, 9))
    # check if the infra already exists — pass without creating if it does
    try:
      i = r.find(infra_name)
      if i:
        print(f"Infrastructure '{infra_name}' already exists")
        return
    except DuploError:
      pass
    name = infra_name
    print(f"Creating infra '{name}'")
    duplo.wait = True
    try:
      r.create({
        "Name": name,
        "Accountid": "",
        "EnableK8Cluster": True,
        "AzCount": 2,
        "Vnet": {
          "SubnetCidr": 22,
          "AddressPrefix": f"11.1{vnum}0.0.0/16"
        },
        "Cloud": 0,
        "OnPremConfig": None,
        "Region": "us-east-2",
        "CustomData": [],
      })
    except DuploFailedResource as e:
      pytest.fail(f"Infrastructure is in a failed state: {e}")
    except DuploError as e:
      pytest.fail(f"Failed to create tenant: {e}")
    
  @pytest.mark.integration
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
