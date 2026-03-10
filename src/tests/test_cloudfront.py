import pytest
import time
from duplocloud.errors import DuploError
from .conftest import get_test_data

@pytest.fixture(scope="class")
def cloudfront_resource(duplo, request):
    """Fixture to load the CloudFront resource and resolve the S3 origin domain.

    The S3 bucket created by TestS3 is used as the CloudFront origin so that
    the OAI / bucket-backend setup is exercised rather than a stub domain.
    """
    resource = duplo.load("cloudfront")
    resource.duplo.wait = True
    tenant = resource.tenant["AccountName"]
    short_name = get_test_data("s3")["Name"]
    bucket_name = f"duploservices-{tenant}-{short_name}"
    request.cls.cloudfront_id = None
    request.cls.origin_domain = f"{bucket_name}.s3.amazonaws.com"
    return resource

def execute_test(func, *args, **kwargs):
    """Helper function to execute a test and handle errors."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")

@pytest.mark.integration
@pytest.mark.aws
@pytest.mark.cloudfront
@pytest.mark.usefixtures("cloudfront_resource")
class TestCloudFront:

    @pytest.mark.dependency(name="create_cloudfront", depends=["create_s3"], scope="session")
    @pytest.mark.order(90)
    def test_create_cloudfront(self, cloudfront_resource, request):
        """Test creating a CloudFront distribution and store ID at class level."""
        r = cloudfront_resource
        body = get_test_data("cloudfront-create")
        origin = body["DistributionConfig"]["Origins"]["Items"][0]
        origin["DomainName"] = self.origin_domain
        origin["Id"] = self.origin_domain
        body["DistributionConfig"]["DefaultCacheBehavior"]["TargetOriginId"] = (
            self.origin_domain
        )
        body["UseOAIIdentity"] = True
        response = execute_test(r.create, body=body)
        status_response = execute_test(r.get_status, distribution_id=response["Id"])
        assert status_response == "Deployed", "CloudFront distribution not deployed"
        request.cls.cloudfront_id = response["Id"]
        print(f"CloudFront Created! ID: {request.cls.cloudfront_id}")

    @pytest.mark.dependency(depends=["create_cloudfront"], scope="session")
    @pytest.mark.order(91)
    def test_update_cloudfront(self, cloudfront_resource, request):
        """Test updating a CloudFront distribution using stored CloudFront ID."""
        r = cloudfront_resource
        assert self.cloudfront_id is not None, "CloudFront ID not found! Ensure test_create_cloudfront ran successfully."
        update_body = get_test_data("cloudfront-update")
        cloudfront = execute_test(r.find, distribution_id=self.cloudfront_id)
        update_body["Id"] = self.cloudfront_id
        update_body["UseOAIIdentity"] = True
        update_body["DistributionConfig"]["CallerReference"] = (
            cloudfront["Distribution"]["DistributionConfig"]["CallerReference"]
        )
        origin = update_body["DistributionConfig"]["Origins"]["Items"][0]
        origin["DomainName"] = self.origin_domain
        origin["Id"] = self.origin_domain
        update_body["DistributionConfig"]["DefaultCacheBehavior"]["TargetOriginId"] = (
            self.origin_domain
        )
        response = execute_test(r.update, body=update_body)
        status_response = execute_test(r.get_status, distribution_id=response["Id"])
        assert status_response == "Deployed", "CloudFront distribution not deployed after update"

    @pytest.mark.dependency(depends=["create_cloudfront"], scope="session")
    @pytest.mark.order(92)
    def test_list_cloudfront(self, cloudfront_resource):
        """Test listing CloudFront distributions."""
        r = cloudfront_resource
        distributions = execute_test(r.list)
        assert isinstance(distributions, list), "CloudFront list response is not a list"
        assert len(distributions) > 0, "No CloudFront distributions found"

    @pytest.mark.dependency(depends=["create_cloudfront"], scope="session")
    @pytest.mark.order(93)
    def test_disable_cloudfront(self, cloudfront_resource):
        """Test disabling a CloudFront distribution."""
        r = cloudfront_resource
        assert self.cloudfront_id is not None, "CloudFront ID not found!"
        execute_test(r.disable, distribution_id=self.cloudfront_id)
        status_response = execute_test(r.get_status, distribution_id=self.cloudfront_id)
        assert status_response == "Deployed", "CloudFront distribution was not disabled"

    @pytest.mark.dependency(depends=["create_cloudfront"], scope="session")
    @pytest.mark.order(94)
    def test_enable_cloudfront(self, cloudfront_resource):
        """Test enabling a CloudFront distribution."""
        r = cloudfront_resource
        assert self.cloudfront_id is not None, "CloudFront ID not found!"
        execute_test(r.enable, distribution_id=self.cloudfront_id)
        status_response = execute_test(r.get_status, distribution_id=self.cloudfront_id)
        assert status_response == "Deployed", "CloudFront distribution was not enabled"
        execute_test(r.disable, distribution_id=self.cloudfront_id)

    @pytest.mark.dependency(depends=["create_cloudfront"], scope="session")
    @pytest.mark.order(997)
    def test_delete_cloudfront(self, cloudfront_resource):
        """Test deleting a CloudFront distribution."""
        r = cloudfront_resource
        assert self.cloudfront_id is not None, "CloudFront ID not found!"
        response = execute_test(r.delete, distribution_id=self.cloudfront_id)
        assert response.get("message") == f"CloudFront distribution {self.cloudfront_id} deleted"
