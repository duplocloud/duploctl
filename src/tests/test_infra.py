import math
import pytest
import random

from duplocloud.client import DuploClient
from duplocloud.errors import DuploError, DuploFailedResource

class TestInfra:

  # def setup_class(self):
  #   inc = random.randint(1, 100)
  #   self.infra_name = f"duploctl{inc}"

  @pytest.mark.integration
  def test_listing_infrastructures(self, duplo: DuploClient):
    r = duplo.load("infrastructure")
    try:
      lot = r("list")
    except DuploError as e:
      pytest.fail(f"Failed to list infrastructures: {e}")

  @pytest.mark.integration
  def test_finding_infra(self, duplo: DuploClient):
    r = duplo.load("tenant")
    try:
      t = r("find", "default")
    except DuploError as e:
      pytest.fail(f"Failed to find default infra: {e}")
    assert t["AccountName"] == "default"

  @pytest.mark.integration
  @pytest.mark.dependency(name = "create_infra", scope='session')
  @pytest.mark.order(1)
  def test_creating_infrastructures(self, duplo: DuploClient, infra_name: str, e2e: bool):
    r = duplo.load("infrastructure")
    vnum = math.ceil(random.randint(1, 9))
    if e2e:
      duplo.tenant = infra_name
    # check if the infra already exists
    try:
      i = r.find(infra_name)
      if i:
        pytest.skip(f"Infrastructure '{infra_name}' already exists")
    except DuploError as e:
      pass
    name = infra_name
    print(f"Creating infra '{name}'")
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
      }, wait=True)
    except DuploFailedResource as e:
      pytest.fail(f"Infrastructure is in a failed state: {e}")
    except DuploError as e:
      pytest.fail(f"Failed to create tenant: {e}")
    
  @pytest.mark.integration
  @pytest.mark.dependency(depends=["create_infra"], scope='session')
  @pytest.mark.order(999)
  def test_find_delete_infra(self, duplo: DuploClient, infra_name: str):
    r = duplo.load("infrastructure")
    # name = self.infra_name
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
