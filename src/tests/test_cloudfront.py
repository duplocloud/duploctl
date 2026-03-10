import pytest
import time
from duplocloud.errors import DuploError
from .conftest import get_test_data
from .test_s3 import _resolve_bucket_name

_CF_COMMENT = "duplo-cloudfront"
# Module-level state persists across fixture resets between non-contiguous tests
_STATE = {"cloudfront_id": None}


def _resolve_cloudfront_id(resource, origin_domain) -> str:
    """Find an existing CloudFront distribution by its S3 origin domain."""
    if not origin_domain:
        return None
    dists = resource.list()
    for d in dists:
        origins = d.get("Origins", {}).get("Items", [])
        for o in origins:
            if o.get("DomainName") == origin_domain:
                return d.get("Id")
    return None


@pytest.fixture(scope="class")
def cloudfront_resource(duplo, request):
    """Fixture to load the CloudFront resource and resolve the S3 origin domain.

    The S3 bucket created by TestS3 is used as the CloudFront origin so that
    the OAI / bucket-backend setup is exercised rather than a stub domain.
    The bucket name is resolved at fixture time by listing, since DuploCloud
    appends the AWS account ID to the bucket name.
    """
    resource = duplo.load("cloudfront")
    resource.duplo.wait = True
    s3 = duplo.load("s3")
    bucket_name = _resolve_bucket_name(s3)
    origin_domain = f"{bucket_name}.s3.amazonaws.com" if bucket_name else None
    existing_id = _resolve_cloudfront_id(resource, origin_domain)
    # Prefer previously-stored ID (survives fixture reset); fall back to list lookup
    if not existing_id and _STATE["cloudfront_id"]:
        existing_id = _STATE["cloudfront_id"]
    request.cls.origin_domain = origin_domain
    request.cls.cloudfront_id = existing_id
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
        assert self.origin_domain, "S3 origin domain not resolved — ensure TestS3 ran first"
        if self.cloudfront_id:
            _STATE["cloudfront_id"] = self.cloudfront_id
            print(f"CloudFront distribution '{self.cloudfront_id}' already exists")
            return
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
        _STATE["cloudfront_id"] = response["Id"]
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
        cfg = cloudfront["Distribution"]["DistributionConfig"]
        update_body["DistributionConfig"]["CallerReference"] = cfg["CallerReference"]
        update_body["DistributionConfig"]["Comment"] = cfg["Comment"]
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
        # Re-resolve the ID in case the class-scoped fixture was reset
        # between non-contiguous tests (orders 94 and 997).
        dist_id = self.cloudfront_id or _STATE["cloudfront_id"] or _resolve_cloudfront_id(r, self.origin_domain)
        assert dist_id is not None, "CloudFront ID not found!"
        response = execute_test(r.delete, distribution_id=dist_id)
        assert response.get("message") == f"CloudFront distribution {dist_id} deleted"
