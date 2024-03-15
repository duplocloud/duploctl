import math
import pytest
import random

from duplocloud.errors import DuploError, DuploFailedResource
from duplocloud.client import DuploClient

duplo, _ = DuploClient.from_env()

@pytest.mark.integration
def test_listing_infrastructures():
  r = duplo.load("infrastructure")
  try:
    lot = r("list")
  except DuploError as e:
    pytest.fail(f"Failed to list infrastructures: {e}")

@pytest.mark.integration
def test_finding_infra():
  r = duplo.load("tenant")
  try:
    t = r("find", "default")
  except DuploError as e:
    pytest.fail(f"Failed to find default infra: {e}")
  assert t["AccountName"] == "default"

@pytest.mark.integration
def test_creating_infrastructures():
  r = duplo.load("infrastructure")
  inc = random.randint(1, 100)
  vnum = math.ceil(random.randint(1, 9))
  name = f"duploctl{inc}"
  try:
    r.create({
      "Name": name,
      "Accountid": "",
      "EnableK8Cluster": False,
      "AzCount": 2,
      "Vnet": { 
        "SubnetCidr": 22, 
        "AddressPrefix": f"11.1{vnum}0.0.0/16"
      },
      "Cloud": 0,
      "OnPremConfig": None,
      "Region": "us-east-1",
      "CustomData": [],
    }, wait=True)
  except DuploFailedResource as e:
    pytest.fail(f"Infrastructure is in a failed state: {e}")
  except DuploError as e:
    pytest.fail(f"Failed to create tenant: {e}")
  try:
    i = r.find(name)
    assert i["Name"] == name
  except DuploError as e:
    pytest.fail(f"Failed to find infrastructure {name}: {e}")
  try:
    r("delete", name)
  except DuploError as e:
    pytest.fail(f"Failed to delete infrastructure: {e}")

