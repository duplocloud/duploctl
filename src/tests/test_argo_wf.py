import pytest
from duplo_resource.argo_wf import DuploArgoWorkflow, _namespace
from duplocloud.commander import get_command_schema


MOCK_TENANT = {
    "TenantId": "tenant-123",
    "AccountName": "test-tenant",
    "PlanID": "test-plan",
}

MOCK_SYSTEM_INFO = {"ResourceNamePrefix": "duploservices"}


def _setup(mocker):
    """Create DuploArgoWorkflow with mocked DuploCtl and DuploArgoClient."""
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

    resource = DuploArgoWorkflow(mock_duplo)
    return resource, mock_argo_client


@pytest.mark.unit
def test_list(mocker):
    argo, client = _setup(mocker)
    client.get.return_value = mocker.MagicMock(json=lambda: {"items": []})
    result = argo.list()
    assert "items" in result
    client.get.assert_called_once_with(
        f"workflows/{_namespace(argo)}", argo.tenant_id
    )


@pytest.mark.unit
def test_find(mocker):
    argo, client = _setup(mocker)
    client.get.return_value = mocker.MagicMock(
        json=lambda: {"metadata": {"name": "wf1"}}
    )
    result = argo.find("wf1")
    assert result["metadata"]["name"] == "wf1"
    client.sanitize_path_segment.assert_called_once_with("wf1")
    client.get.assert_called_once()


@pytest.mark.unit
def test_create(mocker):
    argo, client = _setup(mocker)
    client.post.return_value = mocker.MagicMock(
        json=lambda: {"metadata": {"name": "new-wf"}}
    )
    body = {"workflow": {}}
    result = argo.create(body)
    assert result["metadata"]["name"] == "new-wf"
    # _ensure_namespace injects namespace into body in-place
    assert body["workflow"]["metadata"]["namespace"] == _namespace(argo)
    client.post.assert_called_once_with(
        f"workflows/{_namespace(argo)}", argo.tenant_id, body
    )


@pytest.mark.unit
def test_status(mocker):
    argo, client = _setup(mocker)
    client.get.return_value = mocker.MagicMock(
        json=lambda: {
            "status": {
                "phase": "Succeeded",
                "progress": "1/1",
                "nodes": {"wf1": {"id": "wf1"}},
                "storedTemplates": {"t1": {}},
            }
        }
    )
    result = argo.status("wf1")
    assert result["phase"] == "Succeeded"
    assert result["progress"] == "1/1"
    assert "nodes" not in result
    assert "storedTemplates" not in result


@pytest.mark.unit
def test_delete(mocker):
    argo, client = _setup(mocker)
    client.delete.return_value = mocker.MagicMock(json=lambda: {})
    result = argo.delete("wf1")
    assert result == {}
    client.sanitize_path_segment.assert_called_once_with("wf1")
    client.delete.assert_called_once()


@pytest.mark.unit
def test_apply_creates_when_not_found(mocker):
    argo, client = _setup(mocker)
    # find raises 404 → apply falls through to create
    from duplocloud.errors import DuploError
    client.get.side_effect = DuploError("not found", 404)
    client.post.return_value = mocker.MagicMock(
        json=lambda: {"metadata": {"name": "new-wf"}}
    )
    result = argo.apply({"workflow": {"metadata": {"name": "new-wf"}}})
    assert result["metadata"]["name"] == "new-wf"
    client.post.assert_called_once()


@pytest.mark.unit
def test_logs_no_stream(mocker):
    argo, client = _setup(mocker)
    lines = [
        '{"result":{"content":"Hello","podName":"wf1-pod"}}',
        '{"result":{"content":"World","podName":"wf1-pod"}}',
    ]
    client.get.return_value = mocker.MagicMock(
        iter_lines=lambda decode_unicode=False: iter(lines)
    )
    result = argo.logs("wf1")
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["result"]["content"] == "Hello"
    client.get.assert_called_once_with(
        f"workflows/{_namespace(argo)}/wf1/log",
        argo.tenant_id,
        stream=True,
        params={
            "logOptions.container": "main",
            "logOptions.follow": "false",
        },
    )


@pytest.mark.unit
def test_logs_stream(mocker):
    argo, client = _setup(mocker)
    lines = [
        '{"result":{"content":"Hello","podName":"wf1-pod"}}',
        '{"result":{"content":"World","podName":"wf1-pod"}}',
    ]
    client.get.return_value = mocker.MagicMock(
        iter_lines=lambda decode_unicode=False: iter(lines)
    )
    result = argo.logs("wf1", stream=True)
    assert len(result) == 2
    assert result[1]["result"]["content"] == "World"
    client.get.assert_called_once_with(
        f"workflows/{_namespace(argo)}/wf1/log",
        argo.tenant_id,
        stream=True,
        params={"logOptions.container": "main"},
    )


# Alias resolution tests
@pytest.mark.unit
def test_alias_get_resolves_to_find():
    assert get_command_schema(DuploArgoWorkflow, "get")["method"] == "find"


@pytest.mark.unit
def test_alias_get_workflow_resolves_to_find():
    assert get_command_schema(DuploArgoWorkflow, "get_workflow")["method"] == "find"


@pytest.mark.unit
def test_alias_submit_resolves_to_create():
    assert get_command_schema(DuploArgoWorkflow, "submit")["method"] == "create"


@pytest.mark.unit
def test_alias_list_workflows_resolves_to_list():
    assert get_command_schema(DuploArgoWorkflow, "list_workflows")["method"] == "list"


@pytest.mark.unit
def test_alias_delete_workflow_resolves_to_delete():
    assert get_command_schema(DuploArgoWorkflow, "delete_workflow")["method"] == "delete"
