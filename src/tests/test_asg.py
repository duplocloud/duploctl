import pytest
import time
from duplocloud.errors import DuploError

@pytest.fixture(scope="class")
def asg_resource(duplo):
    """Fixture to load the ASG resource and define ASG name."""
    resource = duplo.load("asg")
    tenant = resource.tenant["AccountName"]
    asg_name = f"duploservices-{tenant}-duploctl"
    return resource, asg_name

def execute_test(func, *args, **kwargs):
    """Helper function to execute a test and handle errors."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")

class TestAsg:

    @pytest.mark.integration
    @pytest.mark.dependency(name="create_asg", scope="session")
    @pytest.mark.order(1)
    def test_create_asg(self, asg_resource):
        r, asg_name = asg_resource
        body = {
            "FriendlyName": asg_name,
            "Zone": 1,
            "IsEbsOptimized": False,
            "DesiredCapacity": 1,
            "MinSize": 1,
            "MaxSize": 2,
            "MetaData": [
                {"Key": "OsDiskSize", "Value": 30},
                {"Key": "MetadataServiceOption", "Value": "enabled_v2_only"}
            ],
            "UseLaunchTemplate": True,
            "CanScaleFromZero": False,
            "IsUserDataCombined": True,
            "KeyPairType": None,
            "Capacity": "t3.small",
            "Base64UserData": "",
            "TagsCsv": "",
            "AgentPlatform": 7,
            "IsClusterAutoscaled": True,
            "IsMinion": True
        }
        execute_test(r.create, body, wait=True)
        time.sleep(60)

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_asg"], scope="session")
    @pytest.mark.order(2)
    def test_find_asg(self, asg_resource):
        r, asg_name = asg_resource
        asg = execute_test(r.find, asg_name)
        assert asg["FriendlyName"] == asg_name

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_asg"], scope="session")
    @pytest.mark.order(3)
    def test_update_asg(self, asg_resource):
        r, asg_name = asg_resource
        body = {"FriendlyName": asg_name, "MinSize": 2, "MaxSize": 3}
        response = execute_test(r.update, body)
        assert "Successfully updated asg" in response["message"]

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_asg"], scope="session")
    @pytest.mark.order(4)
    def test_list_asgs(self, asg_resource):
        r, _ = asg_resource
        asgs = execute_test(r.list)
        assert isinstance(asgs, list) and len(asgs) > 0

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_asg"], scope="session")
    @pytest.mark.order(5)
    def test_scale_asg(self, asg_resource):
        r, asg_name = asg_resource
        response = execute_test(r.scale, asg_name, min=1, max=2)
        assert "Successfully updated asg" in response["message"]

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_asg"], scope="session")
    @pytest.mark.order(6)
    def test_delete_asg(self, asg_resource):
        r, _ = asg_resource
        response = execute_test(r.delete, "duploctl")
        assert "Successfully deleted asg" in response["message"]
