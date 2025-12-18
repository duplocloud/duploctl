import pytest
from unittest.mock import patch
from duplo_resource.argo_wf import DuploArgoWorkflow
from duplocloud.commander import aliased_method

# Patch target for requests - imported inside _make_request method
REQUESTS_PATCH_TARGET = 'requests.request'


def _setup_argo_resource(mocker):
    """Helper to create ArgoWorkflow resource with mocked client."""
    mock_client = mocker.MagicMock()
    mock_client.host = "https://test.duplocloud.net"
    mock_client.token = "test-token"
    mock_client.timeout = 60
    mock_client.tenantid = None
    # Mock resource_prefix property (now on DuploClient)
    type(mock_client).resource_prefix = mocker.PropertyMock(return_value="msi")
    # Mock validate_response to return the response passed to it
    mock_client.validate_response.side_effect = lambda r, *args: r
    # Mock tenant service
    mock_tenant_svc = mocker.MagicMock()
    mock_tenant_svc.find.return_value = {"TenantId": "tenant-123", "AccountName": "test-tenant", "PlanID": "test-plan"}
    # Mock infrastructure service
    mock_infra_svc = mocker.MagicMock()
    mock_infra_svc.find.return_value = {
        "CustomData": [{"Key": "DuploCiTenant", "Value": "ci-tenant-id"}]
    }
    # Return appropriate service based on load call
    def load_service(name):
        if name == "tenant":
            return mock_tenant_svc
        elif name == "infrastructure":
            return mock_infra_svc
        return mocker.MagicMock()
    mock_client.load.side_effect = load_service
    # Mock auth response
    mock_auth = mocker.MagicMock()
    mock_auth.json.return_value = {"Token": "argo-token", "IsAdmin": True, "TenantId": "ctrl-tenant"}
    mock_client.post.return_value = mock_auth
    # Mock system info response (kept for backwards compatibility with other tests)
    mock_system = mocker.MagicMock()
    mock_system.json.return_value = {"ResourceNamePrefix": "msi"}
    mock_client.get.return_value = mock_system
    return DuploArgoWorkflow(mock_client), mock_client


@pytest.mark.unit
def test_auth(mocker):
    argo, mock_client = _setup_argo_resource(mocker)
    result = argo.auth()
    assert result["Token"] == "argo-token"
    mock_client.post.assert_called_once()


@pytest.mark.unit
def test_list(mocker):
    argo, _ = _setup_argo_resource(mocker)
    with patch(REQUESTS_PATCH_TARGET) as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"items": []})
        result = argo.list()
        assert "items" in result


@pytest.mark.unit
def test_find(mocker):
    argo, _ = _setup_argo_resource(mocker)
    with patch(REQUESTS_PATCH_TARGET) as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"metadata": {"name": "wf1"}})
        result = argo.find("wf1")
        assert result["metadata"]["name"] == "wf1"


@pytest.mark.unit
def test_create(mocker):
    argo, _ = _setup_argo_resource(mocker)
    with patch(REQUESTS_PATCH_TARGET) as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"metadata": {"name": "new-wf"}})
        result = argo.create({"workflow": {}})
        assert result["metadata"]["name"] == "new-wf"


@pytest.mark.unit
def test_delete(mocker):
    argo, _ = _setup_argo_resource(mocker)
    with patch(REQUESTS_PATCH_TARGET) as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {})
        result = argo.delete("wf1")
        assert result == {}


# Alias resolution tests
@pytest.mark.unit
def test_alias_get_resolves_to_find():
    """Test that 'get' alias resolves to 'find' method."""
    method = aliased_method(DuploArgoWorkflow, "get")
    assert method == "find"


@pytest.mark.unit
def test_alias_get_workflow_resolves_to_find():
    """Test that 'get_workflow' alias resolves to 'find' method."""
    method = aliased_method(DuploArgoWorkflow, "get_workflow")
    assert method == "find"


@pytest.mark.unit
def test_alias_submit_resolves_to_create():
    """Test that 'submit' alias resolves to 'create' method."""
    method = aliased_method(DuploArgoWorkflow, "submit")
    assert method == "create"


@pytest.mark.unit
def test_alias_list_workflows_resolves_to_list():
    """Test that 'list_workflows' alias resolves to 'list' method."""
    method = aliased_method(DuploArgoWorkflow, "list_workflows")
    assert method == "list"


@pytest.mark.unit
def test_alias_delete_workflow_resolves_to_delete():
    """Test that 'delete_workflow' alias resolves to 'delete' method."""
    method = aliased_method(DuploArgoWorkflow, "delete_workflow")
    assert method == "delete"


# Test aliases work via command() method
@pytest.mark.unit
def test_command_get_alias(mocker):
    """Test that calling command('get') works via alias."""
    argo, _ = _setup_argo_resource(mocker)
    with patch(REQUESTS_PATCH_TARGET) as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"metadata": {"name": "wf1"}})
        cmd = argo.command("get")
        result = cmd("wf1")
        assert result["metadata"]["name"] == "wf1"


@pytest.mark.unit
def test_command_submit_alias(mocker, tmp_path):
    """Test that calling command('submit') works via alias."""
    argo, _ = _setup_argo_resource(mocker)
    # Create a temp file for the body input
    body_file = tmp_path / "workflow.yaml"
    body_file.write_text('{"workflow": {}}')
    with patch(REQUESTS_PATCH_TARGET) as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"metadata": {"name": "new-wf"}})
        cmd = argo.command("submit")
        result = cmd("-f", str(body_file))
        assert result["metadata"]["name"] == "new-wf"


@pytest.mark.unit
def test_command_list_workflows_alias(mocker):
    """Test that calling command('list_workflows') works via alias."""
    argo, _ = _setup_argo_resource(mocker)
    with patch(REQUESTS_PATCH_TARGET) as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"items": []})
        cmd = argo.command("list_workflows")
        result = cmd()
        assert "items" in result
