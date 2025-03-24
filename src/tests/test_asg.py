import pytest
import time
from duplocloud.errors import DuploError

class TestAsg:

    @pytest.mark.integration
    @pytest.mark.dependency(name="create_asg", scope="session")
    @pytest.mark.order(1)
    def test_create_asg(self, duplo):
        r = duplo.load("asg")
        body = {
            "FriendlyName": "duploctl",
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
        try:
            r.create(body, wait=True)
        except DuploError as e:
            pytest.fail(f"Failed to create ASG: {e}")
        time.sleep(60)

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_asg"], scope="session")
    @pytest.mark.order(2)
    def test_find_asg(self, duplo):
        r = duplo.load("asg")
        tenant = r.tenant["AccountName"]
        try:
            asg = r.find(f"duploservices-{tenant}-duploctl")
        except DuploError as e:
            pytest.fail(f"Failed to find ASG: {e}")
        assert asg["FriendlyName"] == f"duploservices-{tenant}-duploctl"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_asg"], scope="session")
    @pytest.mark.order(3)
    def test_update_asg(self, duplo):
        r = duplo.load("asg")
        tenant = r.tenant["AccountName"]
        body = {
            "FriendlyName": f"duploservices-{tenant}-duploctl",
            "MinSize": 2,
            "MaxSize": 3
        }
        try:
            response = r.update(body)
        except DuploError as e:
            pytest.fail(f"Failed to update ASG: {e}")
        assert "Successfully updated asg" in response["message"]

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_asg"], scope="session")
    @pytest.mark.order(4)
    def test_list_asgs(self, duplo):
        r = duplo.load("asg")
        try:
            asgs = r.list()
        except DuploError as e:
            pytest.fail(f"Failed to list ASGs: {e}")
        assert isinstance(asgs, list)
        assert len(asgs) > 0

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_asg"], scope="session")
    @pytest.mark.order(5)
    def test_scale_asg(self, duplo):
        r = duplo.load("asg")
        tenant = r.tenant["AccountName"]
        try:
            response = r.scale(f"duploservices-{tenant}-duploctl", min=1, max=2)
        except DuploError as e:
            pytest.fail(f"Failed to scale ASG: {e}")
        assert "Successfully updated asg" in response["message"]

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_asg"], scope="session")
    @pytest.mark.order(6)
    def test_delete_asg(self, duplo):
        r = duplo.load("asg")
        try:
            response = r.delete("duploctl")
        except DuploError as e:
            pytest.fail(f"Failed to delete ASG: {e}")
        assert "Successfully deleted asg" in response["message"]
