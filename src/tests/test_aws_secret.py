import pytest
import time
from duplocloud.errors import DuploError

@pytest.fixture(scope="class")
def aws_secret_resource(duplo):
    """Fixture to load the AWS Secret resource and define the secret name."""
    resource = duplo.load("aws_secret")
    resource.duplo.wait = True
    tenant = resource.tenant["AccountName"]
    secret_name = f"duploservices-{tenant}-secret"
    return resource, secret_name

def execute_test(func, *args, **kwargs):
    """Helper function to execute a test and handle errors."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")

class TestAwsSecret:

    @pytest.mark.integration
    @pytest.mark.dependency(name="create_secret", scope="session")
    @pytest.mark.order(1)
    def test_create_secret(self, aws_secret_resource):
        """Test creating an AWS secret."""
        r, secret_name = aws_secret_resource
        body = {"Name": secret_name, "SecretString": '{"foo": "bar"}'}
        execute_test(r.create, name=secret_name, body=body)
        time.sleep(10)

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_secret"], scope="session")
    @pytest.mark.order(2)
    def test_find_secret(self, aws_secret_resource):
        """Test finding the created AWS secret."""
        r, secret_name = aws_secret_resource
        secret = execute_test(r.find, secret_name, show_sensitive=True)
        assert secret["Name"] == secret_name
        assert secret["SecretString"] == '{"foo": "bar"}'

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_secret"], scope="session")
    @pytest.mark.order(3)
    def test_update_secret(self, aws_secret_resource):
        """Test updating an AWS secret and verifying the update."""
        r, secret_name = aws_secret_resource
        new_value = '{"foo": "baz"}'
        execute_test(r.update, name=secret_name, value=new_value)
        # Verify the updated value
        updated_secret = execute_test(r.find, secret_name, show_sensitive=True)
        assert "SecretString" in updated_secret, "SecretString key missing in response"
        assert updated_secret["SecretString"] == new_value

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_secret"], scope="session")
    @pytest.mark.order(4)
    def test_delete_secret(self, aws_secret_resource):
        """Test deleting an AWS secret."""
        r, secret_name = aws_secret_resource
        response = execute_test(r.delete, secret_name)
        assert response.get("message") == f"Successfully deleted secret '{secret_name}'"
