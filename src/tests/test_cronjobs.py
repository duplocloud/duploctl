import pytest
import pytest_order

from duplocloud.errors import DuploError
from .helpers import get_test_data

@pytest.fixture()
def cronjob():
  return get_test_data("cronjob")

class TestCronjobs:

  @pytest.mark.integration
  @pytest.mark.order(4)
  @pytest.mark.dependency(name="create_cronjob")
  def test_creating_cronjobs(self, duplo, cronjob):
    name = cronjob["metadata"]["name"]
    r = duplo.load("cronjob")
    try:
      r.create(cronjob, wait=True)
      print(f"Cronjob '{name}' created")
    except DuploError as e:
      pytest.fail(f"Failed to create tenant: {e}")

  @pytest.mark.integration
  @pytest.mark.order(5)
  @pytest.mark.dependency(name="find_cronjob", depends=["create_cronjob"])
  def test_find_cronjob(self, duplo):
    name = "duploctl"
    r = duplo.load("cronjob")
    try:
      o = r.find(name)
      assert o["metadata"]["name"] == name
      print(f"Found cronjob '{name}'")
    except DuploError as e:
      pytest.fail(f"Failed to find cronjob {name}: {e}")
  
  @pytest.mark.integration
  @pytest.mark.order(6)
  @pytest.mark.dependency(name="update_cronjob_image", depends=["find_cronjob"])
  def test_update_image(self, duplo):
    name = "duploctl"
    r = duplo.load("cronjob")
    try:
      r.update_image(name, "ubuntu:latest")
      o = r.find(name)
      assert o["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["image"] == "ubuntu:latest"
    except DuploError as e:
      pytest.fail(f"Failed to find tenant {name}: {e}")
  
  @pytest.mark.integration
  @pytest.mark.dependency(name="update_cronjob_schedule", depends=["create_cronjob"], scope='session')
  @pytest.mark.order(7)
  def test_update_schedule(self, duplo):
    name = "duploctl"
    r = duplo.load("cronjob")
    try:
      r.update_schedule(name, "1 1 * * 0")
      o = r.find(name)
      assert o["spec"]["schedule"] == "1 1 * * 0"
    except DuploError as e:
      pytest.fail(f"Failed to find tenant {name}: {e}")
  
  @pytest.mark.integration
  @pytest.mark.k8s
  @pytest.mark.dependency(name="delete_cronjob", depends=["find_cronjob"])
  @pytest.mark.order(8)
  def test_delete_cronjob(self, duplo):
    r = duplo.load("cronjob")
    try:
      r.delete("duploctl")
    except DuploError as e:
      pytest.fail(f"Failed to delete cronjob: {e}")

