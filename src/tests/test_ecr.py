import pytest
from duplocloud.errors import DuploError
from duplo_resource.ecr import DuploECR, ECR_RESOURCE_TYPE
from .conftest import get_test_data


def _make_ecr(mocker):
    """Create a DuploECR instance with a mocked duplo client."""
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = False
    mock_duplo.validate = False
    ecr = DuploECR(mock_duplo)
    ecr._tenant = {"AccountName": "myaccount", "TenantId": "tid-123"}
    ecr._tenant_id = "tid-123"
    return ecr


def _mock_cloud_svc(mocker, ecr, resources):
    """Replace _cloud_resource with a mock returning the given resources."""
    mock_cloud_svc = mocker.MagicMock()
    mock_cloud_svc.list.return_value = resources
    mock_cloud_svc.find.side_effect = lambda name, rtype: next(
        (r for r in resources if r.get("Name") == name), None
    ) or (_ for _ in ()).throw(DuploError("not found", 404))
    mock_cloud_svc.name_from_body.side_effect = lambda b: b.get("Name")
    ecr._cloud_resource = mock_cloud_svc
    return mock_cloud_svc


# --- name_from_body ---

@pytest.mark.unit
def test_name_from_body(mocker):
    """name_from_body returns the Name key from the body."""
    ecr = _make_ecr(mocker)
    assert ecr.name_from_body({"Name": "myrepo"}) == "myrepo"


@pytest.mark.unit
def test_name_from_body_missing(mocker):
    """name_from_body returns None when Name is absent."""
    ecr = _make_ecr(mocker)
    assert ecr.name_from_body({}) is None


# --- list ---

@pytest.mark.unit
def test_list_delegates_to_cloud_resource_with_type(mocker):
    """list calls cloud_resource.list with ECR_RESOURCE_TYPE."""
    ecr = _make_ecr(mocker)
    mock_cloud_svc = _mock_cloud_svc(mocker, ecr, [
        {"Name": "myrepo", "ResourceType": ECR_RESOURCE_TYPE},
    ])

    result = ecr.list()

    mock_cloud_svc.list.assert_called_once_with(ECR_RESOURCE_TYPE)
    assert len(result) == 1


@pytest.mark.unit
def test_list_empty_when_no_ecr(mocker):
    """list returns empty list when cloud_resource returns none."""
    ecr = _make_ecr(mocker)
    _mock_cloud_svc(mocker, ecr, [])

    assert ecr.list() == []


# --- find ---

@pytest.mark.unit
def test_find_delegates_to_cloud_resource_with_type(mocker):
    """find calls cloud_resource.find with name and ECR_RESOURCE_TYPE."""
    ecr = _make_ecr(mocker)
    repo = {"Name": "myrepo", "ResourceType": ECR_RESOURCE_TYPE}
    mock_cloud_svc = mocker.MagicMock()
    mock_cloud_svc.find.return_value = repo
    ecr._cloud_resource = mock_cloud_svc

    result = ecr.find("myrepo")

    mock_cloud_svc.find.assert_called_once_with("myrepo", ECR_RESOURCE_TYPE)
    assert result == repo


@pytest.mark.unit
def test_find_raises_404_when_not_found(mocker):
    """find raises DuploError 404 when cloud_resource.find raises."""
    ecr = _make_ecr(mocker)
    mock_cloud_svc = mocker.MagicMock()
    mock_cloud_svc.find.side_effect = DuploError("not found", 404)
    ecr._cloud_resource = mock_cloud_svc

    with pytest.raises(DuploError) as exc_info:
        ecr.find("missing")
    assert exc_info.value.code == 404


# --- create ---

@pytest.mark.unit
def test_create_injects_resource_type(mocker):
    """create always sets ResourceType to ECR_RESOURCE_TYPE."""
    ecr = _make_ecr(mocker)
    mock_client = mocker.MagicMock()
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {"Name": "myrepo", "ResourceType": 17}
    mock_client.post.return_value = mock_response
    mocker.patch.object(ecr, "client", mock_client)

    body = {"Name": "myrepo", "EnableTagImmutability": False}
    ecr.create(body)

    posted_body = mock_client.post.call_args[0][1]
    assert posted_body["ResourceType"] == ECR_RESOURCE_TYPE


@pytest.mark.unit
def test_create_preserves_body_fields(mocker):
    """create preserves all user-supplied body fields."""
    ecr = _make_ecr(mocker)
    mock_client = mocker.MagicMock()
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {}
    mock_client.post.return_value = mock_response
    mocker.patch.object(ecr, "client", mock_client)

    body = {
        "Name": "myrepo",
        "EnableTagImmutability": True,
        "EnableScanImageOnPush": True,
    }
    ecr.create(body)

    posted_body = mock_client.post.call_args[0][1]
    assert posted_body["Name"] == "myrepo"
    assert posted_body["EnableTagImmutability"] is True
    assert posted_body["EnableScanImageOnPush"] is True


# --- integration ---

@pytest.fixture(scope="class")
def ecr_resource(duplo):
    """Fixture to load the ECR resource."""
    resource = duplo.load("ecr")
    resource.duplo.wait = True
    return resource


def execute_test(func, *args, **kwargs):
    """Helper to run a resource method and fail the test on DuploError."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")


@pytest.mark.integration
@pytest.mark.aws
@pytest.mark.ecr
@pytest.mark.usefixtures("ecr_resource")
class TestECR:

    @pytest.mark.dependency(
        name="create_ecr", depends=["create_tenant"], scope="session"
    )
    @pytest.mark.order(60)
    def test_create_ecr(self, ecr_resource):
        """Create an ECR repository from the test data file."""
        r = ecr_resource
        body = get_test_data("ecr")
        existing = [
            x for x in r.list()
            if r.name_from_body(x) == body["Name"]
        ]
        if existing:
            print(f"ECR repo '{body['Name']}' already exists")
            return
        response = execute_test(r.create, body=body)
        assert response is not None

    @pytest.mark.dependency(
        name="find_ecr", depends=["create_ecr"], scope="session"
    )
    @pytest.mark.order(61)
    def test_find_ecr(self, ecr_resource):
        """Find the created ECR repository by name."""
        r = ecr_resource
        name = get_test_data("ecr")["Name"]
        repo = execute_test(r.find, name)
        assert repo["Name"] == name

    @pytest.mark.dependency(depends=["find_ecr"], scope="session")
    @pytest.mark.order(62)
    def test_list_ecr(self, ecr_resource):
        """Verify the repo appears in the tenant ECR list."""
        r = ecr_resource
        name = get_test_data("ecr")["Name"]
        repos = execute_test(r.list)
        names = [r.name_from_body(x) for x in repos]
        assert name in names

    @pytest.mark.dependency(depends=["create_ecr"], scope="session")
    @pytest.mark.order(994)
    def test_delete_ecr(self, ecr_resource):
        """Delete the ECR repository created during this test session."""
        r = ecr_resource
        name = get_test_data("ecr")["Name"]
        try:
            execute_test(r.delete, name)
        except DuploError as e:
            if e.code == 404:
                print(f"ECR repo '{name}' already deleted")
            else:
                pytest.fail(f"Failed to delete ECR repo: {e}")
