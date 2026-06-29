import pytest
from duplocloud.errors import DuploError, DuploNotFound
from duplo_resource.workspace import DuploWorkspace


_WORKSPACE_ID = "6a0db3da984d2b398701bca7"
_WORKSPACE_NAME = "platform"
_AGENT_ID = "agent-abc-123"


def _make_workspace(mocker):
    """Create a DuploWorkspace instance with a mocked duplo client."""
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = False
    mock_duplo.host = "https://example.duplocloud.net"
    mock_duplo.timeout = 30
    wksp = DuploWorkspace(mock_duplo)
    wksp._tenant = {"AccountName": "myaccount", "TenantId": "tid-123"}
    wksp._tenant_id = "tid-123"
    return wksp


def _make_client(mocker, wksp, get_responses):
    """Wire a mock client returning the supplied GET JSON payloads in order."""
    mock_client = mocker.MagicMock()
    get_mocks = [mocker.MagicMock() for _ in get_responses]
    for m, payload in zip(get_mocks, get_responses):
        m.json.return_value = payload
    mock_client.get.side_effect = get_mocks
    mocker.patch.object(wksp, "client", mock_client)
    return mock_client


_LIST_RESPONSE = {
    "success": True,
    "data": {
        "items": [
            {"id": _WORKSPACE_ID, "name": _WORKSPACE_NAME},
            {"id": "other-id", "name": "other"},
        ],
    },
}

_DETAIL_RESPONSE = {
    "success": True,
    "data": {"id": _WORKSPACE_ID, "name": _WORKSPACE_NAME},
}


@pytest.mark.unit
def test_list_unwraps_envelope(mocker):
    wksp = _make_workspace(mocker)
    client = _make_client(mocker, wksp, get_responses=[_LIST_RESPONSE])

    result = wksp.list()

    assert result == _LIST_RESPONSE["data"]["items"]
    assert "workspaces" in client.get.call_args[0][0]


@pytest.mark.unit
def test_find_by_name_case_insensitive(mocker):
    wksp = _make_workspace(mocker)
    client = _make_client(mocker, wksp, get_responses=[_LIST_RESPONSE])

    result = wksp.find(name="PLATFORM")

    assert result["id"] == _WORKSPACE_ID
    # name lookup uses the filtered list endpoint
    assert "filters[name]=PLATFORM" in client.get.call_args[0][0]


@pytest.mark.unit
def test_find_by_id_hits_endpoint_directly(mocker):
    wksp = _make_workspace(mocker)
    client = _make_client(mocker, wksp, get_responses=[_DETAIL_RESPONSE])

    result = wksp.find(id=_WORKSPACE_ID)

    assert result["id"] == _WORKSPACE_ID
    assert client.get.call_args[0][0].endswith(f"/workspaces/{_WORKSPACE_ID}")


@pytest.mark.unit
def test_find_requires_name_or_id(mocker):
    wksp = _make_workspace(mocker)
    _make_client(mocker, wksp, get_responses=[])

    with pytest.raises(DuploError, match="name or --id"):
        wksp.find()


@pytest.mark.unit
def test_find_by_name_not_found(mocker):
    wksp = _make_workspace(mocker)
    empty = {"success": True, "data": {"items": []}}
    _make_client(mocker, wksp, get_responses=[empty])

    with pytest.raises(DuploNotFound):
        wksp.find(name="nope")


@pytest.mark.unit
def test_delete(mocker):
    wksp = _make_workspace(mocker)
    client = _make_client(mocker, wksp, get_responses=[_DETAIL_RESPONSE])

    result = wksp.delete(id=_WORKSPACE_ID)

    client.delete.assert_called_once()
    assert client.delete.call_args[0][0].endswith(
        f"/workspaces/{_WORKSPACE_ID}")
    assert "deleted" in result["message"]


@pytest.mark.unit
def test_add_agent(mocker):
    wksp = _make_workspace(mocker)
    agent_svc = wksp.duplo.load("agent")  # same mock used internally
    agent_svc.find.return_value = {"id": _AGENT_ID, "name": "cicd"}
    client = _make_client(mocker, wksp, get_responses=[_DETAIL_RESPONSE])

    result = wksp.add_agent(id=_WORKSPACE_ID, agent_name="cicd")

    client.post.assert_called_once()
    assert client.post.call_args[0][0].endswith(
        f"/workspaces/{_WORKSPACE_ID}/agents/{_AGENT_ID}")
    assert "added" in result["message"]


@pytest.mark.unit
def test_remove_agent(mocker):
    wksp = _make_workspace(mocker)
    agent_svc = wksp.duplo.load("agent")
    agent_svc.find.return_value = {"id": _AGENT_ID, "name": "cicd"}
    client = _make_client(mocker, wksp, get_responses=[_DETAIL_RESPONSE])

    result = wksp.remove_agent(id=_WORKSPACE_ID, agent_id=_AGENT_ID)

    client.delete.assert_called_once()
    assert client.delete.call_args[0][0].endswith(
        f"/workspaces/{_WORKSPACE_ID}/agents/{_AGENT_ID}")
    assert "removed" in result["message"]


@pytest.mark.unit
def test_create(mocker):
    wksp = _make_workspace(mocker)
    client = _make_client(mocker, wksp, get_responses=[])
    client.post.return_value.json.return_value = _DETAIL_RESPONSE

    result = wksp.create(body={"name": _WORKSPACE_NAME})

    client.post.assert_called_once()
    assert client.post.call_args[0][0].endswith("/workspaces")
    assert client.post.call_args[0][1] == {"name": _WORKSPACE_NAME}
    assert result["id"] == _WORKSPACE_ID


@pytest.mark.unit
def test_update_resolves_id_from_body_name(mocker):
    wksp = _make_workspace(mocker)
    client = _make_client(mocker, wksp, get_responses=[_LIST_RESPONSE])
    client.put.return_value.json.return_value = _DETAIL_RESPONSE

    result = wksp.update(body={"name": _WORKSPACE_NAME, "description": "x"})

    client.put.assert_called_once()
    url, body = client.put.call_args[0]
    assert url.endswith(f"/workspaces/{_WORKSPACE_ID}")
    # id must be injected into the body so the backend excludes self from the
    # name-uniqueness check.
    assert body["id"] == _WORKSPACE_ID
    assert result["id"] == _WORKSPACE_ID


@pytest.mark.unit
def test_update_requires_body(mocker):
    wksp = _make_workspace(mocker)
    _make_client(mocker, wksp, get_responses=[])

    with pytest.raises(DuploError, match="body"):
        wksp.update(name=_WORKSPACE_NAME)


@pytest.mark.unit
def test_apply_updates_when_found(mocker):
    wksp = _make_workspace(mocker)
    client = _make_client(mocker, wksp,
                          get_responses=[_LIST_RESPONSE, _LIST_RESPONSE])
    client.put.return_value.json.return_value = _DETAIL_RESPONSE

    result = wksp.apply(body={"name": _WORKSPACE_NAME})

    client.put.assert_called_once()
    client.post.assert_not_called()
    assert result["id"] == _WORKSPACE_ID


@pytest.mark.unit
def test_apply_creates_when_not_found(mocker):
    wksp = _make_workspace(mocker)
    empty = {"success": True, "data": {"items": []}}
    client = _make_client(mocker, wksp, get_responses=[empty])
    client.post.return_value.json.return_value = _DETAIL_RESPONSE

    result = wksp.apply(body={"name": "brand-new"})

    client.post.assert_called_once()
    client.put.assert_not_called()
    assert result["id"] == _WORKSPACE_ID


@pytest.mark.unit
def test_apply_requires_body(mocker):
    # Omitting -f yields body=None; apply() should raise a clear DuploError
    # instead of an AttributeError from body.get(...).
    wksp = _make_workspace(mocker)
    _make_client(mocker, wksp, get_responses=[])

    with pytest.raises(DuploError, match="body"):
        wksp.apply(body=None)
