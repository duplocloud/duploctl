import pytest
from duplocloud.errors import DuploError, DuploNotFound
from duplo_resource.agent import DuploAgent


_AGENT_ID = "agent-abc-123"
_AGENT_NAME = "cicd"


def _make_agent(mocker):
    """Create a DuploAgent instance with a mocked duplo client."""
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = False
    mock_duplo.host = "https://example.duplocloud.net"
    mock_duplo.timeout = 30
    agent = DuploAgent(mock_duplo)
    agent._tenant = {"AccountName": "myaccount", "TenantId": "tid-123"}
    agent._tenant_id = "tid-123"
    return agent


def _make_client(mocker, agent, get_responses):
    """Wire a mock client returning the supplied GET JSON payloads in order."""
    mock_client = mocker.MagicMock()
    get_mocks = [mocker.MagicMock() for _ in get_responses]
    for m, payload in zip(get_mocks, get_responses):
        m.json.return_value = payload
    mock_client.get.side_effect = get_mocks
    mocker.patch.object(agent, "client", mock_client)
    return mock_client


# The list and single-agent endpoints return the same object shape, so the
# list item is a full agent record (including metaData).
_AGENT_FULL = {
    "id": _AGENT_ID,
    "name": _AGENT_NAME,
    "doesSupportStreaming": False,  # top-level lies; metaData is truth
    "metaData": {"STREAMING_ENABLED": "true"},
}

_LIST_RESPONSE = {"success": True, "data": {"items": [_AGENT_FULL]}}

_DETAIL_STREAMING = {"success": True, "data": _AGENT_FULL}

_DETAIL_NON_STREAMING = {
    "success": True,
    "data": {**_AGENT_FULL, "metaData": {"STREAMING_ENABLED": "false"}},
}


@pytest.mark.unit
def test_find_by_name_returns_list_item(mocker):
    agent = _make_agent(mocker)
    client = _make_client(mocker, agent, get_responses=[_LIST_RESPONSE])

    result = agent.find(name="CICD")

    # Single GET — the list item is the full object, no re-fetch by id.
    assert client.get.call_count == 1
    assert "filters[name]=CICD" in client.get.call_args[0][0]
    assert result["id"] == _AGENT_ID
    assert result["metaData"]["STREAMING_ENABLED"] == "true"


@pytest.mark.unit
def test_find_by_id_hits_endpoint_directly(mocker):
    agent = _make_agent(mocker)
    client = _make_client(mocker, agent, get_responses=[_DETAIL_STREAMING])

    result = agent.find(id=_AGENT_ID)

    assert result["id"] == _AGENT_ID
    assert client.get.call_args[0][0].endswith(f"/aiagents/{_AGENT_ID}")


@pytest.mark.unit
def test_find_requires_name_or_id(mocker):
    agent = _make_agent(mocker)
    _make_client(mocker, agent, get_responses=[])

    with pytest.raises(DuploError, match="name or --id"):
        agent.find()


@pytest.mark.unit
def test_find_by_name_not_found(mocker):
    agent = _make_agent(mocker)
    empty = {"success": True, "data": {"items": []}}
    _make_client(mocker, agent, get_responses=[empty])

    with pytest.raises(DuploNotFound):
        agent.find(name="nope")


@pytest.mark.unit
def test_supports_streaming_true_from_metadata(mocker):
    agent = _make_agent(mocker)
    _make_client(mocker, agent, get_responses=[_DETAIL_STREAMING])

    assert agent.supports_streaming(id=_AGENT_ID) is True


@pytest.mark.unit
def test_supports_streaming_by_name_reads_metadata(mocker):
    # The list item carries metaData, so supports_streaming(name) reads it
    # from the single list GET without a second by-id fetch.
    agent = _make_agent(mocker)
    client = _make_client(mocker, agent, get_responses=[_LIST_RESPONSE])

    assert agent.supports_streaming(name="cicd") is True
    assert client.get.call_count == 1


@pytest.mark.unit
def test_supports_streaming_false_from_metadata(mocker):
    agent = _make_agent(mocker)
    _make_client(mocker, agent, get_responses=[_DETAIL_NON_STREAMING])

    assert agent.supports_streaming(id=_AGENT_ID) is False


@pytest.mark.unit
def test_delete(mocker):
    agent = _make_agent(mocker)
    client = _make_client(mocker, agent, get_responses=[_DETAIL_STREAMING])

    result = agent.delete(id=_AGENT_ID)

    client.delete.assert_called_once()
    assert client.delete.call_args[0][0].endswith(f"/aiagents/{_AGENT_ID}")
    assert "deleted" in result["message"]


@pytest.mark.unit
def test_create(mocker):
    agent = _make_agent(mocker)
    client = _make_client(mocker, agent, get_responses=[])
    client.post.return_value.json.return_value = _DETAIL_STREAMING

    result = agent.create(body={"name": _AGENT_NAME})

    client.post.assert_called_once()
    assert client.post.call_args[0][0].endswith("/aiagents")
    assert client.post.call_args[0][1] == {"name": _AGENT_NAME}
    assert result["id"] == _AGENT_ID


@pytest.mark.unit
def test_update_resolves_id_from_body_name(mocker):
    agent = _make_agent(mocker)
    client = _make_client(mocker, agent, get_responses=[_LIST_RESPONSE])
    client.put.return_value.json.return_value = _DETAIL_STREAMING

    result = agent.update(body={"name": _AGENT_NAME, "description": "x"})

    client.put.assert_called_once()
    url, body = client.put.call_args[0]
    assert url.endswith(f"/aiagents/{_AGENT_ID}")
    # id must be injected into the body so the backend excludes self from the
    # name-uniqueness check.
    assert body["id"] == _AGENT_ID
    assert result["id"] == _AGENT_ID


@pytest.mark.unit
def test_update_requires_body(mocker):
    agent = _make_agent(mocker)
    _make_client(mocker, agent, get_responses=[])

    with pytest.raises(DuploError, match="body"):
        agent.update(name=_AGENT_NAME)


@pytest.mark.unit
def test_apply_updates_when_found(mocker):
    agent = _make_agent(mocker)
    client = _make_client(mocker, agent,
                          get_responses=[_LIST_RESPONSE, _LIST_RESPONSE])
    client.put.return_value.json.return_value = _DETAIL_STREAMING

    result = agent.apply(body={"name": _AGENT_NAME})

    client.put.assert_called_once()
    client.post.assert_not_called()
    assert result["id"] == _AGENT_ID


@pytest.mark.unit
def test_apply_creates_when_not_found(mocker):
    agent = _make_agent(mocker)
    empty = {"success": True, "data": {"items": []}}
    client = _make_client(mocker, agent, get_responses=[empty])
    client.post.return_value.json.return_value = _DETAIL_STREAMING

    result = agent.apply(body={"name": "newagent"})

    client.post.assert_called_once()
    client.put.assert_not_called()
    assert result["id"] == _AGENT_ID
