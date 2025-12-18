import pytest
from unittest.mock import patch
from duplo_resource.argo_wf import DuploArgoWorkflowTemplate
from duplocloud.commander import aliased_method

# Patch target for requests - imported inside _make_request method
REQUESTS_PATCH_TARGET = 'requests.request'


def _setup_argo_template_resource(mocker):
    """Helper to create ArgoWorkflowTemplate resource with mocked client."""
    mock_client = mocker.MagicMock()
    mock_client.host = "https://test.duplocloud.net"
    mock_client.token = "test-token"
    mock_client.timeout = 60
    mock_client.tenantid = None
    # Mock system_info for resource_prefix
    mock_client.system_info = {"ResourceNamePrefix": "msi"}
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
    return DuploArgoWorkflowTemplate(mock_client), mock_client


@pytest.mark.unit
def test_list(mocker):
    tpl, _ = _setup_argo_template_resource(mocker)
    with patch(REQUESTS_PATCH_TARGET) as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"items": []})
        result = tpl.list()
        assert "items" in result


@pytest.mark.unit
def test_find(mocker):
    tpl, _ = _setup_argo_template_resource(mocker)
    with patch(REQUESTS_PATCH_TARGET) as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"metadata": {"name": "tpl1"}})
        result = tpl.find("tpl1")
        assert result["metadata"]["name"] == "tpl1"


@pytest.mark.unit
def test_create(mocker):
    tpl, _ = _setup_argo_template_resource(mocker)
    with patch(REQUESTS_PATCH_TARGET) as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"metadata": {"name": "tpl"}})
        result = tpl.create({"template": {}})
        assert result["metadata"]["name"] == "tpl"


@pytest.mark.unit
def test_delete(mocker):
    tpl, _ = _setup_argo_template_resource(mocker)
    with patch(REQUESTS_PATCH_TARGET) as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {})
        result = tpl.delete("tpl")
        assert result == {}
