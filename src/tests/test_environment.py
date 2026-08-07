import pytest
from duplo_resource.helpdesk_client import unwrap_items
from duplocloud.errors import DuploError, DuploNotFound
from duplo_resource.environment import DuploEnvironment


_WORKSPACE_ID = "6a0db3da984d2b398701bca7"
_WORKSPACE_NAME = "platform"
_ENV_ID = "8c2fd5fc106f4d5ba923dec9"
_ENV_NAME = "dev"


def _make_environment(mocker, workspace_id=_WORKSPACE_ID):
    """Create a DuploEnvironment with a mocked client + workspace scope."""
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = False
    mock_duplo.host = "https://example.duplocloud.net"
    mock_duplo.timeout = 30
    mock_duplo.workspace = _WORKSPACE_NAME
    mock_duplo.workspaceid = None
    services = {}

    def _load(name):
        return services.setdefault(name, mocker.MagicMock())

    mock_duplo.load.side_effect = _load
    svc = DuploEnvironment(mock_duplo)
    svc._workspace_id = workspace_id
    svc.duplo.load("workspace").find.return_value = {
        "id": _WORKSPACE_ID, "name": _WORKSPACE_NAME}
    return svc


def _make_client(mocker, svc, get_responses):
    """Wire a mock client returning the supplied GET JSON payloads in order."""
    mock_client = mocker.MagicMock()
    get_mocks = [mocker.MagicMock() for _ in get_responses]
    for m, payload in zip(get_mocks, get_responses):
        m.json.return_value = payload
    mock_client.get.side_effect = get_mocks
    # get_items delegates to the ordered get mocks like the real client
    # (which pages through get), so wired responses serve both.
    mock_client.get_items.side_effect = (
        lambda p: unwrap_items(mock_client.get(p).json()))
    mocker.patch.object(svc, "client", mock_client)
    return mock_client


_LIST_RESPONSE = {
    "success": True,
    "data": {
        "items": [
            {"id": _ENV_ID, "name": _ENV_NAME},
            {"id": "other-id", "name": "other"},
        ],
    },
}

_DETAIL_RESPONSE = {
    "success": True,
    "data": {"id": _ENV_ID, "name": _ENV_NAME},
}


@pytest.mark.unit
def test_list_unwraps_envelope(mocker):
    svc = _make_environment(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    result = svc.list()

    assert result == _LIST_RESPONSE["data"]["items"]
    assert client.get.call_args[0][0].endswith(
        f"/workspaces/{_WORKSPACE_ID}/environments")


@pytest.mark.unit
def test_workspace_resolved_lazily_from_global_flag(mocker):
    svc = _make_environment(mocker, workspace_id=None)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    svc.list()

    svc.workspace_svc.find.assert_called_once_with(
        name=_WORKSPACE_NAME, id=None)
    assert client.get.call_args[0][0].endswith(
        f"/workspaces/{_WORKSPACE_ID}/environments")


@pytest.mark.unit
def test_find_by_name_case_insensitive(mocker):
    svc = _make_environment(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    result = svc.find(name="DEV")

    assert result["id"] == _ENV_ID
    assert "filters[name]=DEV" in client.get.call_args[0][0]


@pytest.mark.unit
def test_find_by_id_hits_endpoint_directly(mocker):
    svc = _make_environment(mocker)
    client = _make_client(mocker, svc, get_responses=[_DETAIL_RESPONSE])

    result = svc.find(id=_ENV_ID)

    assert result["id"] == _ENV_ID
    assert client.get.call_args[0][0].endswith(f"/environments/{_ENV_ID}")


@pytest.mark.unit
def test_find_requires_name_or_id(mocker):
    svc = _make_environment(mocker)
    _make_client(mocker, svc, get_responses=[])

    with pytest.raises(DuploError, match="name or --id"):
        svc.find()


@pytest.mark.unit
def test_find_by_name_not_found(mocker):
    svc = _make_environment(mocker)
    empty = {"success": True, "data": {"items": []}}
    _make_client(mocker, svc, get_responses=[empty])

    with pytest.raises(DuploNotFound):
        svc.find(name="nope")


@pytest.mark.unit
def test_create_posts_to_environments_endpoint(mocker):
    svc = _make_environment(mocker)
    client = _make_client(mocker, svc, get_responses=[])
    client.post.return_value.json.return_value = _DETAIL_RESPONSE

    result = svc.create(body={"name": _ENV_NAME})

    client.post.assert_called_once()
    url, body = client.post.call_args[0]
    assert url.endswith(f"/workspaces/{_WORKSPACE_ID}/environments")
    assert body == {"name": _ENV_NAME}
    assert result["id"] == _ENV_ID


@pytest.mark.unit
def test_create_requires_body(mocker):
    svc = _make_environment(mocker)
    _make_client(mocker, svc, get_responses=[])

    with pytest.raises(DuploError, match="body"):
        svc.create(body=None)


@pytest.mark.unit
def test_update_puts_body_as_provided(mocker):
    svc = _make_environment(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])
    client.put.return_value.json.return_value = _DETAIL_RESPONSE

    body = {"name": _ENV_NAME, "description": "x"}
    result = svc.update(body=body)

    client.put.assert_called_once()
    url, sent = client.put.call_args[0]
    assert url.endswith(f"/environments/{_ENV_ID}")
    # The backend stamps the record id from the route, so the body is
    # sent exactly as provided.
    assert sent == body
    assert result["id"] == _ENV_ID


@pytest.mark.unit
def test_apply_creates_when_not_found(mocker):
    svc = _make_environment(mocker)
    empty = {"success": True, "data": {"items": []}}
    client = _make_client(mocker, svc, get_responses=[empty])
    client.post.return_value.json.return_value = _DETAIL_RESPONSE

    result = svc.apply(body={"name": "brand-new"})

    client.post.assert_called_once()
    client.put.assert_not_called()
    assert result["id"] == _ENV_ID


@pytest.mark.unit
def test_apply_requires_name(mocker):
    svc = _make_environment(mocker)
    _make_client(mocker, svc, get_responses=[])

    with pytest.raises(DuploError, match="name"):
        svc.apply(body={})


@pytest.mark.unit
def test_delete(mocker):
    svc = _make_environment(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    result = svc.delete(name=_ENV_NAME)

    client.delete.assert_called_once()
    assert client.delete.call_args[0][0].endswith(
        f"/environments/{_ENV_ID}")
    assert "deleted" in result["message"]
