import pytest
import time
from duplocloud.errors import DuploError
from .conftest import get_test_data

@pytest.fixture(scope="class")
def asg_resource(duplo):
    """Fixture to load the ASG resource and define ASG name."""
    resource = duplo.load("asg")
    resource.duplo.wait = True
    tenant = resource.tenant["AccountName"]
    asg_name = f"duploservices-{tenant}-duploctl"
    return resource, asg_name

def execute_test(func, *args, **kwargs):
    """Helper function to execute a test and handle errors."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")

@pytest.mark.integration
@pytest.mark.aws
@pytest.mark.k8s
@pytest.mark.asg
class TestAsg:

    @pytest.mark.dependency(name="create_asg", depends=["create_tenant"], scope="session")
    @pytest.mark.order(30)
    def test_create_asg(self, asg_resource):
        r, asg_name = asg_resource
        body = get_test_data("asg")
        try:
            existing = r.find(asg_name)
            if existing:
                print(f"ASG '{asg_name}' already exists")
                return
        except DuploError:
            pass
        response = execute_test(r.create, body=body)
        assert response["data"] == asg_name
        time.sleep(60)

    @pytest.mark.dependency(name="find_asg", depends=["create_asg"], scope="session")
    @pytest.mark.order(31)
    def test_find_asg(self, asg_resource):
        r, asg_name = asg_resource
        asg = execute_test(r.find, asg_name)
        assert asg["FriendlyName"] == asg_name

    @pytest.mark.dependency(depends=["create_asg"], scope="session")
    @pytest.mark.order(32)
    def test_update_asg(self, asg_resource):
        r, asg_name = asg_resource
        body = {"FriendlyName": asg_name, "MinSize": 2, "MaxSize": 3}
        response = execute_test(r.update, body=body)
        assert "Successfully updated asg" in response["message"]

    @pytest.mark.dependency(depends=["create_asg"], scope="session")
    @pytest.mark.order(33)
    def test_list_asgs(self, asg_resource):
        r, _ = asg_resource
        asgs = execute_test(r.list)
        assert isinstance(asgs, list) and len(asgs) > 0
        
    @pytest.mark.dependency(depends=["find_asg"], scope="session")
    @pytest.mark.order(34)
    def test_update_allocation_tags(self, asg_resource):
        r, asg_name = asg_resource
        test_tags = "duploctl"
        response = execute_test(r.update_allocation_tags, asg_name, test_tags)
        assert "Successfully updated allocation tag for asg" in response["message"]

    @pytest.mark.dependency(depends=["find_asg"], scope="session")
    @pytest.mark.order(34)
    def test_scale_asg(self, asg_resource):
        r, asg_name = asg_resource
        response = execute_test(r.scale, asg_name, min=1, max=2)
        assert "Successfully updated asg" in response["message"]

    @pytest.mark.dependency(depends=["find_asg"], scope="session")
    @pytest.mark.order(34)
    def test_scale_asg_min_zero(self, asg_resource):
        """Test scaling ASG with minimum size of 0."""
        r, asg_name = asg_resource
        response = execute_test(r.scale, asg_name, min=0)
        assert "Successfully updated asg" in response["message"]

    @pytest.mark.dependency(depends=["find_asg"], scope="session")
    @pytest.mark.order(34)
    def test_scale_asg_max_zero(self, asg_resource):
        """Test scaling ASG with maximum size of 0."""
        r, asg_name = asg_resource
        response = execute_test(r.scale, asg_name, max=0)
        assert "Successfully updated asg" in response["message"]

    @pytest.mark.dependency(depends=["find_asg"], scope="session")
    @pytest.mark.order(34)
    def test_scale_asg_both_zero(self, asg_resource):
        """Test scaling ASG with both min and max size of 0."""
        r, asg_name = asg_resource
        response = execute_test(r.scale, asg_name, min=0, max=0)
        assert "Successfully updated asg" in response["message"]

    @pytest.mark.dependency(depends=["find_asg"], scope="session")
    @pytest.mark.order(34)
    def test_scale_asg_no_params_error(self, asg_resource):
        """Test that scaling ASG with no parameters raises an error."""
        r, asg_name = asg_resource
        with pytest.raises(DuploError, match="Must provide either min or max"):
            r.scale(asg_name)

    @pytest.mark.dependency(name="asg_restored", depends=["find_asg"], scope="session")
    @pytest.mark.order(35)
    def test_restore_asg(self, asg_resource):
        """Restore ASG to min=1 after scale-to-zero tests, so job pods can schedule."""
        r, asg_name = asg_resource
        response = execute_test(r.scale, asg_name, min=1, max=2)
        assert "Successfully updated asg" in response["message"]

    @pytest.mark.dependency(depends=["find_asg"], scope="session")
    @pytest.mark.order(993)
    def test_delete_asg(self, asg_resource):
        r, _ = asg_resource
        response = execute_test(r.delete, "duploctl")
        assert "Successfully deleted asg" in response["message"]
