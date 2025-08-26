import pytest
from duplocloud.errors import DuploError
from .conftest import get_test_data

@pytest.fixture(scope="class")
def configmap_resource(duplo, request):
    """Fixture to load the ConfigMap resource and ensure ConfigMap name persists across tests."""
    resource = duplo.load("configmap")
    request.cls.configmap_name = f"duploctl"
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
    def test_create_configmap(self, configmap_resource):
        """Test creating a ConfigMap with various methods."""
        body = get_test_data("configmap")
        response = execute_test(configmap_resource.create, name=self.configmap_name, body=body)
        assert response["metadata"]["name"] == self.configmap_name
        assert response["data"] == body["data"]
        # Test creating with complete body
        body = {
            "metadata": {"name": f"{self.configmap_name}-2"},
            "data": {"config1": "test1", "config2": "test2"}
        }
        response = execute_test(configmap_resource.create, body=body)
        assert response["metadata"]["name"] == f"{self.configmap_name}-2"
        assert response["data"] == body["data"]
        # Test dryrun option
        dryrun_response = execute_test(configmap_resource.create, name=f"{self.configmap_name}-3", 
                                     data={"test": "value"}, dryrun=True)
        assert dryrun_response["metadata"]["name"] == f"{self.configmap_name}-3"
        assert "data" in dryrun_response

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_configmap"], scope="class")
    @pytest.mark.order(6)
    def test_find_configmap(self, configmap_resource):
        """Test finding a ConfigMap."""
        # Test finding existing ConfigMap
        configmap = execute_test(configmap_resource.find, self.configmap_name)
        assert configmap["metadata"]["name"] == self.configmap_name
        assert "data" in configmap
        assert configmap["data"]["foo"] == "bar"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_configmap"], scope="class")
    @pytest.mark.order(7)
    def test_update_configmap(self, configmap_resource):
        """Test updating a ConfigMap using different methods."""
        # Test updating with new data
        new_data = {"key3": "value3", "key1": "updated1"}
        response = execute_test(configmap_resource.update, name=self.configmap_name, data=new_data)
        assert response["data"]["key3"] == "value3"
        assert response["data"]["key1"] == "updated1"
        assert response["data"]["foo"] == "bar"
        # Test updating with patches
        patches = [
            {'op': 'add', 'path': '/data/new_key', 'value': 'new_value'},
            {'op': 'remove', 'path': '/data/foo', 'value': None},
            {'op': 'replace', 'path': '/data/key1', 'value': 'final_value'}
        ]
        response = execute_test(configmap_resource.update, name=self.configmap_name, patches=patches)
        assert response["data"]["new_key"] == "new_value"
        assert "key2" not in response["data"]
        assert response["data"]["key1"] == "final_value"
        # Test dryrun update
        dryrun_response = execute_test(configmap_resource.update, name=self.configmap_name,
                                     data={"test": "value"}, dryrun=True)
        assert "test" in dryrun_response["data"]

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_configmap"], scope="class")
    @pytest.mark.order(8)
    def test_delete_configmap(self, configmap_resource):
        """Test deleting ConfigMaps and verifying deletion."""
        # Delete first ConfigMap
        response = execute_test(configmap_resource.delete, name=self.configmap_name)
        assert response["message"] == f"Successfully deleted configmap '{self.configmap_name}'"
        # Delete second ConfigMap
        response = execute_test(configmap_resource.delete, name=f"{self.configmap_name}-2")
        assert response["message"] == f"Successfully deleted configmap '{self.configmap_name}-2'"
