import pytest
import time
import yaml
import pathlib
from duplocloud.errors import DuploError
from .conftest import get_test_data

@pytest.fixture(scope="class")
def cloudfront_resource(duplo, request):
    """Fixture to load the CloudFront resource and ensure CloudFront ID persists across tests."""
    resource = duplo.load("cloudfront")
    tenant = resource.tenant["AccountName"]
    request.cls.cloudfront_id = None
    return resource

def execute_test(func, *args, **kwargs):
    """Helper function to execute a test and handle errors."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")

def get_test_data(name) -> dict:
  dir = pathlib.Path(__file__).parent.resolve()
  f = f"{dir}/data/{name}.yaml"
  with open(f, 'r') as stream:
    return yaml.safe_load(stream)

@pytest.mark.usefixtures("cloudfront_resource")
class TestCloudFront:

    @pytest.mark.integration
    @pytest.mark.dependency(name="create_cloudfront", scope="class")
    @pytest.mark.order(5)
    def test_create_cloudfront(self, cloudfront_resource, request):
        """Test creating a CloudFront distribution and store ID at class level."""
        r = cloudfront_resource
        body = get_test_data("cloudfront-create")
        response = execute_test(r.create, body=body, wait=True)
        print(response)
        assert "Distribution" in response, "Missing 'Distribution' key in response"
        assert "Id" in response["Distribution"], "CloudFront distribution ID missing in response"
        assert response["Distribution"]["Status"] == "Deployed", "CloudFront distribution not deployed"
        request.cls.cloudfront_id = response["Distribution"]["Id"]
        print(f"CloudFront Created! ID: {request.cls.cloudfront_id}")
        time.sleep(10)

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_cloudfront"], scope="class")
    @pytest.mark.order(6)
    def test_update_cloudfront(self, cloudfront_resource, request):
        """Test updating a CloudFront distribution using stored CloudFront ID."""
        r = cloudfront_resource
        assert self.cloudfront_id is not None, "CloudFront ID not found! Ensure test_create_cloudfront ran successfully."
        update_body = get_test_data("cloudfront-update")
        cloudfront = execute_test(r.find, distribution_id=self.cloudfront_id)
        update_body["Id"] = self.cloudfront_id
        update_body["DistributionConfig"]["CallerReference"] = cloudfront["Distribution"]["DistributionConfig"]["CallerReference"]
        response = execute_test(r.update, body=update_body, wait=True)
        assert "Distribution" in response, "Missing 'Distribution' key in response"
        assert response["Distribution"]["Id"] == self.cloudfront_id, "CloudFront ID mismatch after update"
        assert response["Distribution"]["Status"] == "Deployed", "CloudFront distribution not deployed after update"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_cloudfront"], scope="session")
    @pytest.mark.order(7)
    def test_list_cloudfront(self, cloudfront_resource):
        """Test listing CloudFront distributions."""
        r = cloudfront_resource
        distributions = execute_test(r.list)
        assert isinstance(distributions, list), "CloudFront list response is not a list"
        assert len(distributions) > 0, "No CloudFront distributions found"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_cloudfront"], scope="session")
    @pytest.mark.order(8)
    def test_disable_cloudfront(self, cloudfront_resource):
        """Test disabling a CloudFront distribution."""
        r = cloudfront_resource
        assert self.cloudfront_id is not None, "CloudFront ID not found!"
        execute_test(r.disable, distribution_id=self.cloudfront_id, wait=True)
        status_response = execute_test(r.get_status, distribution_id=self.cloudfront_id)
        assert status_response == "Deployed", "CloudFront distribution was not disabled"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_cloudfront"], scope="session")
    @pytest.mark.order(9)
    def test_enable_cloudfront(self, cloudfront_resource):
        """Test enabling a CloudFront distribution."""
        r = cloudfront_resource
        assert self.cloudfront_id is not None, "CloudFront ID not found!"
        execute_test(r.enable, distribution_id=self.cloudfront_id, wait=True)
        status_response = execute_test(r.get_status, distribution_id=self.cloudfront_id)
        assert status_response == "Deployed", "CloudFront distribution was not enabled"
        execute_test(r.disable, distribution_id=self.cloudfront_id, wait=True)

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_cloudfront"], scope="session")
    @pytest.mark.order(997)
    def test_delete_cloudfront(self, cloudfront_resource):
        """Test deleting a CloudFront distribution."""
        r = cloudfront_resource
        assert self.cloudfront_id is not None, "CloudFront ID not found!"
        response = execute_test(r.delete, distribution_id=self.cloudfront_id)
        assert response.get("message") == f"CloudFront distribution {self.cloudfront_id} deleted"
