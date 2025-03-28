import pytest
import time
from duplocloud.errors import DuploError
from .conftest import get_test_data

@pytest.fixture(scope="class")
def configmap_resource(duplo, request):
    """Fixture to load the ConfigMap resource and ensure ConfigMap name persists across tests."""
    resource = duplo.load("configmap")
    tenant = resource.tenant["AccountName"]
    request.cls.configmap_name = None
    return resource

def execute_test(func, *args, **kwargs):
    """Helper function to execute a test and handle errors."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")

@pytest.mark.usefixtures("configmap_resource")
class TestConfigMap:

    @pytest.mark.integration
    @pytest.mark.dependency(name="create_configmap", scope="class")
    @pytest.mark.order(5)
    def test_create_configmap(self, configmap_resource, request):
        """Test creating a ConfigMap and store name at class level."""
        r = configmap_resource
        body = get_test_data("configmap")
        response = execute_test(r.create, body=body, wait=True)
        assert "name" in response["metadata"], "ConfigMap name missing in response"
        request.cls.configmap_name = response["metadata"]["name"]

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_configmap"], scope="class")
    @pytest.mark.order(6)
    def test_update_configmap(self, configmap_resource, request):
        """Test updating a ConfigMap using stored ConfigMap name."""
        r = configmap_resource
        assert self.configmap_name is not None, "ConfigMap name not found! Ensure test_create_configmap ran successfully."
        update_body = get_test_data("configmap")
        response = execute_test(r.update, name=self.configmap_name, body=update_body)
        assert "name" in response["metadata"], "ConfigMap name missing in response"
        assert response["metadata"]["name"] == self.configmap_name, "ConfigMap name mismatch after update"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_configmap"], scope="session")
    @pytest.mark.order(7)
    def test_list_configmap(self, configmap_resource):
        """Test listing ConfigMaps."""
        r = configmap_resource
        configmaps = execute_test(r.list)
        assert isinstance(configmaps, list), "ConfigMap list response is not a list"
        assert len(configmaps) > 0, "No ConfigMaps found"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_configmap"], scope="session")
    @pytest.mark.order(997)
    def test_delete_configmap(self, configmap_resource):
        """Test deleting a ConfigMap."""
        r = configmap_resource
        assert self.configmap_name is not None, "ConfigMap name not found!"
        response = execute_test(r.delete, name=self.configmap_name)
        assert response.get("message") == f"Successfully deleted configmap '{self.configmap_name}'"
