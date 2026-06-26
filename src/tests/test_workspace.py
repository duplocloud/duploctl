import pytest
from duplocloud.errors import DuploError, DuploNotFound
from duplo_resource.workspace import DuploWorkspace


_WORKSPACE_ID = "6a0db3da984d2b398701bca7"
_WORKSPACE_NAME = "platform"


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
