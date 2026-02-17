import pytest
from unittest.mock import patch
from duplo_resource.argo_wf import DuploArgoWorkflow
from duplocloud.commander import aliased_method


# A valid JWT token for testing (not expired, exp in 2099)
# Header: {"alg": "HS256", "typ": "JWT"}
# Payload: {"exp": 4102444800, "iat": 1704067200, "sub": "test"}
TEST_JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjQxMDI0NDQ4MDAsImlhdCI6MTcwNDA2NzIwMCwic3ViIjoidGVzdCJ9.test"


def _setup_argo_resource(mocker):
    """Helper to create ArgoWorkflow resource with mocked client."""
    mock_client = mocker.MagicMock()
    mock_client.host = "https://test.duplocloud.net"
    mock_client.token = "test-token"
    mock_client.timeout = 60
    mock_client.tenantid = None
    # Mock validate_response to return the response passed to it
    mock_client.validate_response.side_effect = lambda r, *args: r
    # Mock cache methods with a valid JWT token
    mock_client.cache_key_for.return_value = "test-argo-auth-key"
    mock_client.get_cached_item.return_value = {
        "Token": TEST_JWT_TOKEN, 
        "TenantId": "ctrl-tenant",
        "ExpiresAt": "2099-01-01T00:00:00Z"  # Far future to avoid expiration
    }
    mock_client.set_cached_item.return_value = None
    mock_client.expired.return_value = False  # Token not expired
    # Mock tenant service
    mock_tenant_svc = mocker.MagicMock()
    mock_tenant_svc.find.return_value = {"TenantId": "tenant-123", "AccountName": "test-tenant", "PlanID": "test-plan"}
    # Mock infrastructure service
    mock_infra_svc = mocker.MagicMock()
    mock_infra_svc.find.return_value = {
        "CustomData": [{"Key": "DuploCiTenant", "Value": "ci-tenant-id"}]
    }
    # Mock system service for resource_prefix
    mock_system_svc = mocker.MagicMock()
    mock_system_svc.info.return_value = {"ResourceNamePrefix": "msi"}
    # Return appropriate service based on load call
    def load_service(name):
        if name == "tenant":
            return mock_tenant_svc
        elif name == "infrastructure":
            return mock_infra_svc
        elif name == "system":
            return mock_system_svc
        return mocker.MagicMock()
    mock_client.load.side_effect = load_service
    # Mock auth response
    mock_auth = mocker.MagicMock()
    mock_auth.json.return_value = {"Token": "argo-jwt-token", "IsAdmin": True, "TenantId": "ctrl-tenant"}
    mock_client.post.return_value = mock_auth
    return DuploArgoWorkflow(mock_client), mock_client


@pytest.mark.unit
def test_auth(mocker):
    argo, mock_client = _setup_argo_resource(mocker)
    result = argo.auth()
    assert result["Token"] == TEST_JWT_TOKEN
    # Verify cache was used
    mock_client.cache_key_for.assert_called_with("argo-auth")
    mock_client.get_cached_item.assert_called()


@pytest.mark.unit
def test_list(mocker):
    argo, mock_client = _setup_argo_resource(mocker)
    mock_client.get.return_value = mocker.MagicMock(json=lambda: {"items": []})
    result = argo.list()
    assert "items" in result
    mock_client.get.assert_called_once()
    # Check that custom headers were passed with mergeHeaders=False
    call_args, call_kwargs = mock_client.get.call_args
    assert 'headers' in call_kwargs
    assert 'mergeHeaders' in call_kwargs
    assert call_kwargs['mergeHeaders'] == False
    assert 'Authorization' in call_kwargs['headers']
    assert 'duplotoken' in call_kwargs['headers']


@pytest.mark.unit
def test_find(mocker):
    argo, mock_client = _setup_argo_resource(mocker)
    mock_client.get.return_value = mocker.MagicMock(json=lambda: {"metadata": {"name": "wf1"}})
    result = argo.find("wf1")
    assert result["metadata"]["name"] == "wf1"
    mock_client.get.assert_called_once()
    # Verify path sanitization was called
    mock_client.sanitize_path_segment.assert_called_once_with("wf1")


@pytest.mark.unit
def test_create(mocker):
    argo, mock_client = _setup_argo_resource(mocker)
    # Mock post to return workflow creation response
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {"metadata": {"name": "new-wf"}}
    mock_client.post.return_value = mock_response
    result = argo.create({"workflow": {}})
    assert result["metadata"]["name"] == "new-wf"
    # post is called for the workflow creation
    mock_client.post.assert_called()


@pytest.mark.unit
def test_delete(mocker):
    argo, mock_client = _setup_argo_resource(mocker)
    mock_client.delete.return_value = mocker.MagicMock(json=lambda: {})
    result = argo.delete("wf1")
    assert result == {}
    mock_client.delete.assert_called_once()


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
    argo, mock_client = _setup_argo_resource(mocker)
    mock_client.get.return_value = mocker.MagicMock(json=lambda: {"metadata": {"name": "wf1"}})
    cmd = argo.command("get")
    result = cmd("wf1")
    assert result["metadata"]["name"] == "wf1"


@pytest.mark.unit
def test_command_submit_alias(mocker, tmp_path):
    """Test that calling command('submit') works via alias."""
    argo, mock_client = _setup_argo_resource(mocker)
    # Create a temp file for the body input
    body_file = tmp_path / "workflow.yaml"
    body_file.write_text('{"workflow": {}}')
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {"metadata": {"name": "new-wf"}}
    mock_client.post.return_value = mock_response
    cmd = argo.command("submit")
    result = cmd("-f", str(body_file))
    assert result["metadata"]["name"] == "new-wf"


@pytest.mark.unit
def test_command_list_workflows_alias(mocker):
    """Test that calling command('list_workflows') works via alias."""
    argo, mock_client = _setup_argo_resource(mocker)
    mock_client.get.return_value = mocker.MagicMock(json=lambda: {"items": []})
    cmd = argo.command("list_workflows")
    result = cmd()
    assert "items" in result
