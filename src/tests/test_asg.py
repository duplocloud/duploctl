import json
import time
from unittest.mock import MagicMock

import pytest

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


# ---------------------------------------------------------------------------
# stop_resources() / start_resources() — snapshot, scale-to-zero, restore
# ---------------------------------------------------------------------------

def _make_asg(mocker):
    """Return a DuploAsg with a mocked client and pinned tenant."""
    from duplo_resource.asg import DuploAsg
    duplo = MagicMock()
    duplo.wait = False
    resource = DuploAsg(duplo)
    resource.client = MagicMock()
    resource._tenant = {"TenantId": "tid-1", "AccountName": "mytenant"}
    resource._tenant_id = "tid-1"
    return resource


def _asg_body(min_size=2, max_size=3, desired=3, autoscaled=False,
              snapshot=None):
    body = {
        "FriendlyName": "duploservices-mytenant-apps",
        "MinSize": min_size, "MaxSize": max_size,
        "DesiredCapacity": desired, "IsClusterAutoscaled": autoscaled,
        "CanScaleFromZero": False, "CustomDataTags": [],
    }
    if snapshot is not None:
        body["CustomDataTags"] = [
            {"Key": "DuploctlSleepState", "Value": snapshot}]
    return body


_SNAP = json.dumps({"MinSize": 2, "MaxSize": 3, "DesiredCapacity": 3,
                    "CanScaleFromZero": False})


@pytest.mark.unit
@pytest.mark.asg
def test_asg_stop_resources_snapshots_then_scales_to_zero(mocker):
    r = _make_asg(mocker)
    mocker.patch.object(r, "list", return_value=[_asg_body()])
    set_cd = mocker.patch.object(r, "_set_custom_data")
    apply = mocker.patch.object(r, "_apply_capacity")

    errors = r.stop_resources()

    assert errors == []
    assert set_cd.call_args.args[1] == r._SLEEP_KEY
    assert json.loads(set_cd.call_args.args[2]) == {
        "MinSize": 2, "MaxSize": 3, "DesiredCapacity": 3,
        "CanScaleFromZero": False}
    # non-autoscaled group: CanScaleFromZero left untouched
    apply.assert_called_once_with(_asg_body(), 0, 0, 0,
                                  can_scale_from_zero=None)


@pytest.mark.unit
@pytest.mark.asg
def test_asg_stop_resources_enables_scale_from_zero_when_autoscaled(mocker):
    r = _make_asg(mocker)
    mocker.patch.object(r, "list", return_value=[_asg_body(autoscaled=True)])
    mocker.patch.object(r, "_set_custom_data")
    apply = mocker.patch.object(r, "_apply_capacity")

    r.stop_resources()

    assert apply.call_args.kwargs["can_scale_from_zero"] is True


@pytest.mark.unit
@pytest.mark.asg
def test_asg_stop_resources_skips_group_already_at_zero(mocker):
    r = _make_asg(mocker)
    asleep = _asg_body(min_size=0, max_size=0, desired=0, snapshot=_SNAP)
    mocker.patch.object(r, "list", return_value=[asleep])
    set_cd = mocker.patch.object(r, "_set_custom_data")
    apply = mocker.patch.object(r, "_apply_capacity")

    assert r.stop_resources() == []
    set_cd.assert_not_called()
    apply.assert_not_called()


@pytest.mark.unit
@pytest.mark.asg
def test_asg_stop_resources_rolls_back_snapshot_on_scale_failure(mocker):
    r = _make_asg(mocker)
    mocker.patch.object(r, "list", return_value=[_asg_body()])
    set_cd = mocker.patch.object(r, "_set_custom_data")
    mocker.patch.object(r, "_apply_capacity",
                        side_effect=DuploError("nope", 400))

    errors = r.stop_resources()

    assert len(errors) == 1
    # the snapshot written before the failed scale is rolled back
    assert any(c.kwargs.get("delete") for c in set_cd.call_args_list)


@pytest.mark.unit
@pytest.mark.asg
def test_asg_start_resources_restores_snapshot_then_clears(mocker):
    r = _make_asg(mocker)
    body = _asg_body(min_size=0, max_size=0, desired=0, snapshot=_SNAP)
    mocker.patch.object(r, "list", return_value=[body])
    apply = mocker.patch.object(r, "_apply_capacity")
    set_cd = mocker.patch.object(r, "_set_custom_data")

    assert r.start_resources() == []
    apply.assert_called_once_with(body, 2, 3, 3, can_scale_from_zero=False)
    assert any(c.kwargs.get("delete") for c in set_cd.call_args_list)


@pytest.mark.unit
@pytest.mark.asg
def test_asg_start_resources_skips_without_snapshot(mocker):
    r = _make_asg(mocker)
    mocker.patch.object(r, "list", return_value=[_asg_body()])
    apply = mocker.patch.object(r, "_apply_capacity")

    assert r.start_resources() == []
    apply.assert_not_called()
