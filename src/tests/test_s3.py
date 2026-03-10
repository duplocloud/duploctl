import pytest
from duplocloud.errors import DuploError
from .conftest import get_test_data


@pytest.fixture(scope="class")
def s3_resource(duplo, request):
    """Fixture to load the S3 resource and store the full bucket name."""
    resource = duplo.load("s3")
    tenant = resource.tenant["AccountName"]
    short_name = get_test_data("s3")["Name"]
    request.cls.bucket_name = f"duploservices-{tenant}-{short_name}"
    return resource


def execute_test(func, *args, **kwargs):
    """Helper to run a resource method and fail the test on DuploError."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")


@pytest.mark.integration
@pytest.mark.aws
@pytest.mark.s3
@pytest.mark.usefixtures("s3_resource")
class TestS3:

    @pytest.mark.dependency(name="create_s3", depends=["create_tenant"], scope="session")
    @pytest.mark.order(50)
    def test_create_s3(self, s3_resource):
        """Create an S3 bucket from the test data file."""
        r = s3_resource
        try:
            existing = r.find(self.bucket_name)
            if existing:
                print(f"S3 bucket '{self.bucket_name}' already exists")
                return
        except DuploError:
            pass
        body = get_test_data("s3")
        response = execute_test(r.create, body=body)
        assert response is not None

    @pytest.mark.dependency(name="find_s3", depends=["create_s3"], scope="session")
    @pytest.mark.order(51)
    def test_find_s3(self, s3_resource):
        """Find the created S3 bucket by its full prefixed name."""
        r = s3_resource
        bucket = execute_test(r.find, self.bucket_name)
        assert bucket["Name"] == self.bucket_name

    @pytest.mark.dependency(depends=["find_s3"], scope="session")
    @pytest.mark.order(52)
    def test_list_s3(self, s3_resource):
        """Verify the bucket appears in the tenant's bucket list."""
        r = s3_resource
        buckets = execute_test(r.list)
        names = [b["Name"] for b in buckets]
        assert self.bucket_name in names

    @pytest.mark.dependency(depends=["create_s3"], scope="session")
    @pytest.mark.order(992)
    def test_delete_s3(self, s3_resource):
        """Delete the S3 bucket created during this test session."""
        r = s3_resource
        try:
            execute_test(r.delete, self.bucket_name)
        except DuploError as e:
            if e.code == 404:
                print(f"S3 bucket '{self.bucket_name}' already deleted")
            else:
                pytest.fail(f"Failed to delete S3 bucket: {e}")
