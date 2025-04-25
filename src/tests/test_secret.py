import pytest
from duplocloud.errors import DuploError
from .conftest import get_test_data

@pytest.fixture(scope="class")
def secret_resource(duplo, request):
    """Fixture to load the Kubernetes Secret resource and define the secret name."""
    resource = duplo.load("secret")
    request.cls.secret_name = f"duploctl"
    return resource

def execute_test(func, *args, **kwargs):
    """Helper function to execute a test and handle errors."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")

class TestSecret:
    """Integration tests for Kubernetes Secrets."""

    @pytest.mark.integration
    @pytest.mark.dependency(name="create_secret", scope="session")
    @pytest.mark.order(1)
    def test_create_secret(self, secret_resource):
        """Test creating a Kubernetes secret."""
        body = get_test_data("secret")
        execute_test(secret_resource.create, name=self.secret_name, body=body)

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_secret"], scope="session")
    @pytest.mark.order(2)
    def test_find_secret(self, secret_resource):
        """Test finding the created Kubernetes secret."""
        secret = execute_test(secret_resource.find, self.secret_name)
        assert secret["SecretName"] == self.secret_name
        assert "SecretData" in secret
        assert "username" in secret["SecretData"]
        assert "password" in secret["SecretData"]
        assert secret["SecretData"]["username"] == "admin"
        assert secret["SecretData"]["password"] == "secret123"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_secret"], scope="session")
    @pytest.mark.order(3)
    def test_update_secret(self, secret_resource):
        """Test updating a Kubernetes secret."""
        new_data = {"api_key": "xyz789","username": "superadmin"}
        execute_test(secret_resource.update,name=self.secret_name,data=new_data)
        # Verify the update
        updated_secret = execute_test(secret_resource.find, self.secret_name)
        assert updated_secret["SecretData"]["api_key"] == "xyz789"
        assert updated_secret["SecretData"]["username"] == "superadmin"
        assert updated_secret["SecretData"]["password"] == "secret123"
        # Test update using patches
        patches = [
            {'op': 'add', 'path': '/SecretData/new_key', 'value': 'new_value'},
            {'op': 'remove', 'path': '/SecretData/password', 'value': None}
        ]
        execute_test(secret_resource.update, name=self.secret_name, patches=patches)
        # Verify patches
        patched_secret = execute_test(secret_resource.find, self.secret_name)
        assert patched_secret["SecretData"]["new_key"] == "new_value"
        assert "password" not in patched_secret["SecretData"]

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_secret"], scope="session")
    @pytest.mark.order(4)
    def test_delete_secret(self, secret_resource):
        """Test deleting a Kubernetes secret."""
        response = execute_test(secret_resource.delete, self.secret_name)
        assert response["message"] == f"Successfully deleted secret 'duploctl'"