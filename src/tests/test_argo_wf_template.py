import pytest
from unittest.mock import patch
from duplo_resource.argo_wf import DuploArgoWorkflowTemplate
from duplocloud.commander import aliased_method


# A valid JWT token for testing (not expired, exp in 2099)
# Header: {"alg": "HS256", "typ": "JWT"}
# Payload: {"exp": 4102444800, "iat": 1704067200, "sub": "test"}
TEST_JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjQxMDI0NDQ4MDAsImlhdCI6MTcwNDA2NzIwMCwic3ViIjoidGVzdCJ9.test"


def _setup_argo_template_resource(mocker):
    """Helper to create ArgoWorkflowTemplate resource with mocked client."""
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
    return DuploArgoWorkflowTemplate(mock_client), mock_client


@pytest.mark.unit
def test_list(mocker):
    tpl, mock_client = _setup_argo_template_resource(mocker)
    mock_client.get.return_value = mocker.MagicMock(json=lambda: {"items": []})
    result = tpl.list()
    assert "items" in result
    mock_client.get.assert_called_once()


@pytest.mark.unit
def test_find(mocker):
    tpl, mock_client = _setup_argo_template_resource(mocker)
    mock_client.get.return_value = mocker.MagicMock(json=lambda: {"metadata": {"name": "tpl1"}})
    result = tpl.find("tpl1")
    assert result["metadata"]["name"] == "tpl1"
    mock_client.get.assert_called_once()
    mock_client.sanitize_path_segment.assert_called_once_with("tpl1")


@pytest.mark.unit
def test_create(mocker):
    tpl, mock_client = _setup_argo_template_resource(mocker)
    # Mock post to return template creation response
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {"metadata": {"name": "tpl"}}
    mock_client.post.return_value = mock_response
    result = tpl.create({"template": {}})
    assert result["metadata"]["name"] == "tpl"
    mock_client.post.assert_called()


@pytest.mark.unit
def test_delete(mocker):
    tpl, mock_client = _setup_argo_template_resource(mocker)
    mock_client.delete.return_value = mocker.MagicMock(json=lambda: {})
    result = tpl.delete("tpl")
    assert result == {}
    mock_client.delete.assert_called_once()
