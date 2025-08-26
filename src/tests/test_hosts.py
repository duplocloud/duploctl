import pytest
import time
from duplocloud.errors import DuploError
from .conftest import get_test_data

@pytest.fixture(scope="class")
def hosts_resource(duplo, request):
    """Fixture to load the Hosts resource and define host name."""
    resource = duplo.load("hosts")
    resource.duplo.wait = True
    tenant = resource.tenant["AccountName"]
    request.cls.host_name = f"duploservices-{tenant}-duplohost"
    return resource

def execute_test(func, *args, **kwargs):
    """Helper function to execute a test and handle errors."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")

class TestHosts:

    @pytest.mark.integration
    @pytest.mark.dependency(name="create_host", scope="session")
    @pytest.mark.order(5)
    def test_create_host(self, hosts_resource):
        body = get_test_data("hosts")
        response = execute_test(hosts_resource.create, body)
        assert "Successfully created host" in response["message"]
        time.sleep(60)

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_host"], scope="session")
    @pytest.mark.order(6)
    def test_find_host(self, hosts_resource):
        host = execute_test(hosts_resource.find, self.host_name)
        assert host["FriendlyName"] == self.host_name
        assert host["Status"] == "running"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_host"], scope="session")
    @pytest.mark.order(7)
    def test_stop_host(self, hosts_resource):
        response = execute_test(hosts_resource.stop, self.host_name)
        assert "Successfully stopped host" in response["message"]
        host = execute_test(hosts_resource.find, self.host_name)
        assert host["Status"] == "stopped"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_host"], scope="session")
    @pytest.mark.order(8)
    def test_start_host(self, hosts_resource):
        response = execute_test(hosts_resource.start, self.host_name)
        assert "Successfully started host" in response["message"]
        host = execute_test(hosts_resource.find, self.host_name)
        assert host["Status"] == "running"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_host"], scope="session")
    @pytest.mark.order(9)
    def test_reboot_host(self, hosts_resource):
        response = execute_test(hosts_resource.reboot, self.host_name)
        assert "Successfully rebooted host" in response["message"]
        time.sleep(60)
        host = execute_test(hosts_resource.find, self.host_name)
        assert host["Status"] == "running"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_host"], scope="session")
    @pytest.mark.order(997)
    def test_delete_host(self, hosts_resource):
        response = execute_test(hosts_resource.delete, self.host_name)
        assert "Successfully deleted host" in response["message"]
