import pytest
from duplo_resource.argo_wf import DuploArgoWorkflowTemplate, _namespace
from duplocloud.errors import DuploError


MOCK_TENANT = {
    "TenantId": "tenant-123",
    "AccountName": "test-tenant",
    "PlanID": "test-plan",
}

MOCK_SYSTEM_INFO = {"ResourceNamePrefix": "duploservices"}


def _setup(mocker):
    """Create DuploArgoWorkflowTemplate with mocked DuploCtl and DuploArgoClient."""
    mock_duplo = mocker.MagicMock()
    mock_duplo.token = "duplo-token"
    mock_duplo.host = "https://test.duplocloud.net"
    mock_duplo.timeout = 60
    mock_duplo.tenantid = None

    # Mock the Argo client injected by @Resource(client="argo_wf")
    mock_argo_client = mocker.MagicMock()
    mock_argo_client.sanitize_path_segment.side_effect = lambda s: s

    # Services loaded by tenant-scope injection and prefix property
    mock_tenant_svc = mocker.MagicMock()
    mock_tenant_svc.find.return_value = MOCK_TENANT

    mock_system_svc = mocker.MagicMock()
    mock_system_svc.info.return_value = MOCK_SYSTEM_INFO

    def load_svc(name):
        if name == "tenant":
            return mock_tenant_svc
        if name == "system":
            return mock_system_svc
        return mocker.MagicMock()

    mock_duplo.load.side_effect = load_svc
    mock_duplo.load_client.return_value = mock_argo_client

    resource = DuploArgoWorkflowTemplate(mock_duplo)
    return resource, mock_argo_client


@pytest.mark.unit
def test_list(mocker):
    tpl, client = _setup(mocker)
    client.get.return_value = mocker.MagicMock(json=lambda: {"items": []})
    result = tpl.list()
    assert "items" in result
    client.get.assert_called_once_with(
        f"workflow-templates/{_namespace(tpl)}", tpl.tenant_id
    )


@pytest.mark.unit
def test_find(mocker):
    tpl, client = _setup(mocker)
    client.get.return_value = mocker.MagicMock(
        json=lambda: {"metadata": {"name": "tpl1"}}
    )
    result = tpl.find("tpl1")
    assert result["metadata"]["name"] == "tpl1"
    client.sanitize_path_segment.assert_called_once_with("tpl1")
    client.get.assert_called_once()


@pytest.mark.unit
def test_create(mocker):
    tpl, client = _setup(mocker)
    client.post.return_value = mocker.MagicMock(
        json=lambda: {"metadata": {"name": "tpl1"}}
    )
    body = {"template": {}}
    result = tpl.create(body)
    assert result["metadata"]["name"] == "tpl1"
    # _ensure_namespace injects namespace into body in-place
    assert body["template"]["metadata"]["namespace"] == _namespace(tpl)
    client.post.assert_called_once_with(
        f"workflow-templates/{_namespace(tpl)}",
        tpl.tenant_id,
        body,
    )


@pytest.mark.unit
def test_update(mocker):
    tpl, client = _setup(mocker)
    # find returns current template with resourceVersion
    client.get.return_value = mocker.MagicMock(
        json=lambda: {
            "metadata": {"name": "tpl1", "resourceVersion": "42"}
        }
    )
    client.put.return_value = mocker.MagicMock(
        json=lambda: {"metadata": {"name": "tpl1"}}
    )
    body = {"template": {"metadata": {"name": "tpl1"}, "spec": {}}}
    result = tpl.update(body)
    assert result["metadata"]["name"] == "tpl1"
    # _ensure_namespace injects namespace and resourceVersion into body
    assert body["template"]["metadata"]["namespace"] == _namespace(tpl)
    assert body["template"]["metadata"]["resourceVersion"] == "42"
    client.put.assert_called_once()


@pytest.mark.unit
def test_update_missing_name(mocker):
    tpl, client = _setup(mocker)
    with pytest.raises(DuploError) as exc:
        tpl.update({"template": {"metadata": {}}})
    assert exc.value.code == 400


@pytest.mark.unit
def test_delete(mocker):
    tpl, client = _setup(mocker)
    client.delete.return_value = mocker.MagicMock(json=lambda: {})
    result = tpl.delete("tpl1")
    assert result == {}
    client.sanitize_path_segment.assert_called_once_with("tpl1")
    client.delete.assert_called_once()


@pytest.mark.unit
def test_apply_creates_when_not_found(mocker):
    tpl, client = _setup(mocker)
    client.get.side_effect = DuploError("not found", 404)
    client.post.return_value = mocker.MagicMock(
        json=lambda: {"metadata": {"name": "tpl1"}}
    )
    result = tpl.apply(
        {"template": {"metadata": {"name": "tpl1"}, "spec": {}}}
    )
    assert result["metadata"]["name"] == "tpl1"
    client.post.assert_called_once()


@pytest.mark.unit
def test_apply_updates_when_exists(mocker):
    tpl, client = _setup(mocker)
    # find succeeds → apply calls update
    client.get.return_value = mocker.MagicMock(
        json=lambda: {
            "metadata": {"name": "tpl1", "resourceVersion": "7"}
        }
    )
    client.put.return_value = mocker.MagicMock(
        json=lambda: {"metadata": {"name": "tpl1"}}
    )
    result = tpl.apply(
        {"template": {"metadata": {"name": "tpl1"}, "spec": {}}}
    )
    assert result["metadata"]["name"] == "tpl1"
    client.put.assert_called_once()


@pytest.mark.unit
def test_delete_empty_body(mocker):
    tpl, client = _setup(mocker)
    mock_response = mocker.MagicMock()
    mock_response.content = b""
    client.delete.return_value = mock_response
    result = tpl.delete("tpl1")
    assert result == {}
    client.delete.assert_called_once()


@pytest.mark.unit
def test_create_missing_body(mocker):
    tpl, client = _setup(mocker)
    with pytest.raises(DuploError) as exc:
        tpl.create(None)
    assert exc.value.code == 400
