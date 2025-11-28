import pytest
from unittest.mock import patch
from duplo_resource.argo_wf import DuploArgoWorkflow


def _setup_argo_resource(mocker):
    """Helper to create ArgoWorkflow resource with mocked client."""
    mock_client = mocker.MagicMock()
    mock_client.host = "https://test.duplocloud.net"
    mock_client.token = "test-token"
    mock_client.timeout = 60
    mock_client.tenantid = None
    mock_tenant_svc = mocker.MagicMock()
    mock_tenant_svc.find.return_value = {"TenantId": "tenant-123", "AccountName": "test-tenant"}
    mock_client.load.return_value = mock_tenant_svc
    # Mock auth response
    mock_auth = mocker.MagicMock()
    mock_auth.json.return_value = {"Token": "argo-token", "IsAdmin": True, "TenantId": "ctrl-tenant"}
    mock_client.post.return_value = mock_auth
    # Mock system info response
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
def test_list_templates(mocker):
    argo, _ = _setup_argo_resource(mocker)
    with patch('requests.request') as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"items": []})
        result = argo.list_templates()
        assert "items" in result


@pytest.mark.unit
def test_get_template(mocker):
    argo, _ = _setup_argo_resource(mocker)
    with patch('requests.request') as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"metadata": {"name": "tpl1"}})
        result = argo.get_template("tpl1")
        assert result["metadata"]["name"] == "tpl1"


@pytest.mark.unit
def test_list_workflows(mocker):
    argo, _ = _setup_argo_resource(mocker)
    with patch('requests.request') as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"items": []})
        result = argo.list_workflows()
        assert "items" in result


@pytest.mark.unit
def test_get_workflow(mocker):
    argo, _ = _setup_argo_resource(mocker)
    with patch('requests.request') as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"metadata": {"name": "wf1"}})
        result = argo.get_workflow("wf1")
        assert result["metadata"]["name"] == "wf1"


@pytest.mark.unit
def test_submit(mocker):
    argo, _ = _setup_argo_resource(mocker)
    with patch('requests.request') as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"metadata": {"name": "new-wf"}})
        result = argo.submit({"workflow": {}})
        assert result["metadata"]["name"] == "new-wf"


@pytest.mark.unit
def test_delete_workflow(mocker):
    argo, _ = _setup_argo_resource(mocker)
    with patch('requests.request') as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {})
        result = argo.delete_workflow("wf1")
        assert result == {}


@pytest.mark.unit
def test_create_template(mocker):
    argo, _ = _setup_argo_resource(mocker)
    with patch('requests.request') as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {"metadata": {"name": "tpl"}})
        result = argo.create_template({"template": {}})
        assert result["metadata"]["name"] == "tpl"


@pytest.mark.unit
def test_delete_template(mocker):
    argo, _ = _setup_argo_resource(mocker)
    with patch('requests.request') as mock_req:
        mock_req.return_value = mocker.MagicMock(status_code=200, json=lambda: {})
        result = argo.delete_template("tpl")
        assert result == {}
