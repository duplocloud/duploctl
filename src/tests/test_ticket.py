import argparse
import json
import io
import pytest
from duplocloud.errors import DuploError
from duplocloud.argtype import StdinTextAction
from duplo_resource.ticket import DuploTicket


_WORKSPACE_ID = "6a0db3da984d2b398701bca7"
_WORKSPACE_NAME = "platform"
_AGENT_ID = "agent-abc-123"
_TICKET_NAME = "DEVOPS-42"


def _make_ticket(mocker, streaming_agent=False):
    """Create a DuploTicket with mocked client and workspace/agent resources."""
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = False
    mock_duplo.host = "https://example.duplocloud.net"
    mock_duplo.timeout = 30

    # Stub the delegated workspace/agent resources before constructing the
    # ticket, since they are loaded eagerly in __init__. Unknown names (e.g.
    # the tenant load from tenant-scope injection) get a generic mock.
    wksp_svc = mocker.MagicMock()
    wksp_svc.find.return_value = {"id": _WORKSPACE_ID, "name": _WORKSPACE_NAME}
    agent_svc = mocker.MagicMock()
    agent_svc.find.return_value = {"id": _AGENT_ID, "name": "cicd"}
    agent_svc.supports_streaming.return_value = streaming_agent
    mock_duplo.load.side_effect = lambda n: {
        "workspace": wksp_svc, "agent": agent_svc}.get(n, mocker.MagicMock())

    ticket = DuploTicket(mock_duplo)
    ticket._tenant = {"AccountName": "myaccount", "TenantId": "tid-123"}
    ticket._tenant_id = "tid-123"
    return ticket, wksp_svc, agent_svc


def _make_client(mocker, ticket, get_responses=None, post_responses=None):
    """Wire a mock client returning GET/POST JSON payloads in order."""
    mock_client = mocker.MagicMock()
    get_mocks = [mocker.MagicMock() for _ in (get_responses or [])]
    for m, payload in zip(get_mocks, get_responses or []):
        m.json.return_value = payload
    mock_client.get.side_effect = get_mocks or None

    post_mocks = [mocker.MagicMock() for _ in (post_responses or [])]
    for m, payload in zip(post_mocks, post_responses or []):
        m.json.return_value = payload
    mock_client.post.side_effect = post_mocks or None

    mocker.patch.object(ticket, "client", mock_client)
    return mock_client


def _fake_sse_response(mocker, sse_lines):
    """Context-managed mock streaming response yielding the given SSE lines."""
    fake_stream = mocker.MagicMock()
    fake_stream.iter_lines.return_value = iter(sse_lines)
    fake_stream.__enter__ = mocker.MagicMock(return_value=fake_stream)
    fake_stream.__exit__ = mocker.MagicMock(return_value=False)
    return fake_stream


_TICKET_RESPONSE = {"success": True, "data": {"name": _TICKET_NAME, "id": "t-1"}}
_TICKET_DETAIL = {
    "success": True,
    "data": {"name": _TICKET_NAME, "id": "t-1", "aiAgentId": _AGENT_ID},
}
_MSG_RESPONSE = {"content": "hi there"}

_SSE_LINES = [
    'data: {"type":"text_delta","text":"Hello "}',
    'data: {"type":"text_delta","text":"world"}',
    'data: {"type":"done"}',
]


@pytest.mark.unit
def test_create_ticket_with_agent_id(mocker):
    ticket, wksp_svc, agent_svc = _make_ticket(mocker)
    client = _make_client(mocker, ticket, post_responses=[_TICKET_RESPONSE])

    result = ticket.create_ticket(
        title="Test", workspace=_WORKSPACE_NAME, agent_id=_AGENT_ID)

    # workspace resolved via the workspace resource, agent lookup skipped
    wksp_svc.find.assert_called_once()
    agent_svc.find.assert_not_called()

    post_url, post_body = client.post.call_args[0]
    assert post_url.endswith(f"/tickets/{_WORKSPACE_ID}")
    assert post_body["aiAgentId"] == _AGENT_ID
    assert post_body["workspaceId"] == _WORKSPACE_ID
    assert result["ticketname"] == _TICKET_NAME
    assert result["chat_url"].endswith(f"/{_WORKSPACE_ID}/tickets/chat/{_TICKET_NAME}")
    assert result["ai_response"] is None


@pytest.mark.unit
def test_create_ticket_with_agent_name_resolves_id(mocker):
    ticket, wksp_svc, agent_svc = _make_ticket(mocker)
    _make_client(mocker, ticket, post_responses=[_TICKET_RESPONSE])

    ticket.create_ticket(
        title="Test", workspace=_WORKSPACE_NAME, agent_name="cicd")

    agent_svc.find.assert_called_once()


@pytest.mark.unit
def test_create_ticket_requires_agent(mocker):
    ticket, _, _ = _make_ticket(mocker)
    _make_client(mocker, ticket, post_responses=[])

    with pytest.raises(DuploError, match="agent_id or --agent_name"):
        ticket.create_ticket(title="Test", workspace=_WORKSPACE_NAME)


@pytest.mark.unit
def test_find_ticket_by_name(mocker):
    ticket, _, _ = _make_ticket(mocker)
    client = _make_client(mocker, ticket, get_responses=[_TICKET_DETAIL])

    result = ticket.find(name=_TICKET_NAME, workspace=_WORKSPACE_NAME)

    assert result["name"] == _TICKET_NAME
    assert client.get.call_args[0][0].endswith(
        f"/tickets/{_WORKSPACE_ID}/{_TICKET_NAME}")


@pytest.mark.unit
def test_find_requires_identifier(mocker):
    ticket, _, _ = _make_ticket(mocker)
    _make_client(mocker, ticket)

    with pytest.raises(DuploError, match="ticket name or --id"):
        ticket.find(workspace=_WORKSPACE_NAME)


@pytest.mark.unit
def test_send_message_unary_when_agent_not_streaming(mocker):
    ticket, _, agent_svc = _make_ticket(mocker, streaming_agent=False)
    client = _make_client(
        mocker, ticket,
        get_responses=[_TICKET_DETAIL],   # _agent_id_from_ticket
        post_responses=[_MSG_RESPONSE],   # unary send
    )

    result = ticket.send_message(
        name=_TICKET_NAME, workspace=_WORKSPACE_NAME, content="hello agent")

    assert client.post.call_count == 1
    assert client.post.call_args[0][0].endswith("/sendMessage")
    assert result["ai_response"]["content"] == "hi there"


@pytest.mark.unit
def test_send_message_unary_recovers_from_ndjson(mocker):
    # A stale STREAMING_ENABLED flag routes a streaming agent to the unary
    # endpoint; the helpdesk 400s but embeds the agent's NDJSON reply in the
    # (JSON-encoded) error body. The reply must be recovered, not surfaced as
    # a raw backend deserialization error.
    ticket, _, _ = _make_ticket(mocker, streaming_agent=False)
    raw = (
        'Error {"type":"executed_tool_calls"}\n'
        '{"type":"text_delta","text":"Hi! "}\n'
        '{"type":"text_delta","text":"there"}\n'
        '{"type":"done"}\n'
        ' in request call to Agent.'
    )
    get_resp = mocker.MagicMock()
    get_resp.json.return_value = _TICKET_DETAIL  # _agent_id_from_ticket
    mock_client = mocker.MagicMock()
    mock_client.get.return_value = get_resp
    # Body is a JSON-encoded string, exactly as the backend returns it.
    mock_client.post.side_effect = DuploError(json.dumps(raw), 400)
    mocker.patch.object(ticket, "client", mock_client)

    result = ticket.send_message(
        name=_TICKET_NAME, workspace=_WORKSPACE_NAME, content="hi")

    assert mock_client.post.call_args[0][0].endswith("/sendMessage")
    assert result["ai_response"]["content"] == "Hi! there"


@pytest.mark.unit
def test_send_message_unary_reraises_unrecoverable_error(mocker):
    # A genuine error (no embedded agent events) must propagate unchanged.
    ticket, _, _ = _make_ticket(mocker, streaming_agent=False)
    get_resp = mocker.MagicMock()
    get_resp.json.return_value = _TICKET_DETAIL
    mock_client = mocker.MagicMock()
    mock_client.get.return_value = get_resp
    mock_client.post.side_effect = DuploError("Ticket not found", 404)
    mocker.patch.object(ticket, "client", mock_client)

    with pytest.raises(DuploError, match="not found"):
        ticket.send_message(
            name=_TICKET_NAME, workspace=_WORKSPACE_NAME, content="hi")


@pytest.mark.unit
def test_send_message_streams_when_agent_supports_streaming(mocker):
    ticket, _, agent_svc = _make_ticket(mocker, streaming_agent=True)
    client = _make_client(mocker, ticket, get_responses=[_TICKET_DETAIL])
    client.post.side_effect = [_fake_sse_response(mocker, _SSE_LINES)]

    result = ticket.send_message(
        name=_TICKET_NAME, workspace=_WORKSPACE_NAME, content="hello")

    stream_call = client.post.call_args
    assert stream_call[0][0].endswith("/sendMessageStreaming")
    assert stream_call[1]["headers"] == {"Accept": "text/event-stream"}
    assert stream_call[1]["stream"] is True
    assert result["ai_response"]["content"] == "Hello world"


@pytest.mark.unit
def test_send_message_streaming_flag_forces_streaming(mocker):
    # agent does NOT advertise streaming, but --streaming forces it
    ticket, _, agent_svc = _make_ticket(mocker, streaming_agent=False)
    client = _make_client(mocker, ticket, get_responses=[_TICKET_DETAIL])
    client.post.side_effect = [_fake_sse_response(mocker, _SSE_LINES)]

    ticket.send_message(
        name=_TICKET_NAME, workspace=_WORKSPACE_NAME,
        content="hello", streaming=True)

    # supports_streaming is short-circuited by the explicit flag
    agent_svc.supports_streaming.assert_not_called()
    assert client.post.call_args[0][0].endswith("/sendMessageStreaming")


@pytest.mark.unit
def test_send_message_requires_content(mocker):
    ticket, _, _ = _make_ticket(mocker)
    _make_client(mocker, ticket)

    with pytest.raises(DuploError, match="content"):
        ticket.send_message(
            name=_TICKET_NAME, workspace=_WORKSPACE_NAME, content="   ")


def _content_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--content", action=StdinTextAction)
    return parser


@pytest.mark.unit
def test_stdin_text_action_returns_literal_unparsed():
    # A colon would be mangled by YAML parsing; raw text is preserved.
    ns = _content_parser().parse_args(["--content", "build broke: see logs"])
    assert ns.content == "build broke: see logs"


@pytest.mark.unit
def test_stdin_text_action_reads_stdin_on_dash(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("piped message\n"))
    ns = _content_parser().parse_args(["--content", "-"])
    assert ns.content == "piped message\n"


@pytest.mark.unit
def test_list_tickets(mocker):
    ticket, wksp_svc, _ = _make_ticket(mocker)
    client = _make_client(
        mocker, ticket, get_responses=[[{"name": _TICKET_NAME}]])

    result = ticket.list(workspace=_WORKSPACE_NAME)

    assert client.get.call_args[0][0].endswith(f"/tickets/{_WORKSPACE_ID}")
    assert result == [{"name": _TICKET_NAME}]


@pytest.mark.unit
def test_assignee(mocker):
    ticket, _, _ = _make_ticket(mocker)
    client = _make_client(
        mocker, ticket, get_responses=[{"id": _AGENT_ID, "name": "cicd"}])

    result = ticket.assignee(name=_TICKET_NAME, workspace=_WORKSPACE_NAME)

    assert client.get.call_args[0][0].endswith(
        f"/tickets/{_WORKSPACE_ID}/{_TICKET_NAME}/assignee")
    assert result["id"] == _AGENT_ID


@pytest.mark.unit
def test_reassign(mocker):
    ticket, _, agent_svc = _make_ticket(mocker)
    client = _make_client(mocker, ticket)

    result = ticket.reassign(
        name=_TICKET_NAME, workspace=_WORKSPACE_NAME, agent_name="cicd")

    client.put.assert_called_once()
    assert client.put.call_args[0][0].endswith(
        f"/tickets/{_WORKSPACE_ID}/{_TICKET_NAME}/assignee/{_AGENT_ID}")
    assert "reassigned" in result["message"]


@pytest.mark.unit
def test_set_status(mocker):
    ticket, _, _ = _make_ticket(mocker)
    client = _make_client(mocker, ticket)
    put_mock = mocker.MagicMock()
    put_mock.json.return_value = {"name": _TICKET_NAME, "status": "inProgress"}
    client.put.return_value = put_mock

    result = ticket.set_status(
        name=_TICKET_NAME, workspace=_WORKSPACE_NAME, status="inProgress")

    url, body = client.put.call_args[0]
    assert url.endswith(f"/tickets/{_WORKSPACE_ID}/{_TICKET_NAME}/status")
    assert body == {"status": "inProgress"}
    assert result["status"] == "inProgress"


@pytest.mark.unit
def test_set_status_requires_status(mocker):
    ticket, _, _ = _make_ticket(mocker)
    _make_client(mocker, ticket)

    with pytest.raises(DuploError, match="status"):
        ticket.set_status(name=_TICKET_NAME, workspace=_WORKSPACE_NAME)


@pytest.mark.unit
def test_set_status_closed_requires_disposition(mocker):
    # The backend rejects closing without a disposition; enforce the documented
    # contract client-side so the user gets a clear error first.
    ticket, _, _ = _make_ticket(mocker)
    client = _make_client(mocker, ticket)

    with pytest.raises(DuploError, match="disposition"):
        ticket.set_status(
            name=_TICKET_NAME, workspace=_WORKSPACE_NAME, status="closed")
    client.put.assert_not_called()


@pytest.mark.unit
def test_set_status_closed_with_disposition(mocker):
    ticket, _, _ = _make_ticket(mocker)
    client = _make_client(mocker, ticket)
    put_mock = mocker.MagicMock()
    put_mock.json.return_value = {"name": _TICKET_NAME, "status": "closed"}
    client.put.return_value = put_mock

    ticket.set_status(
        name=_TICKET_NAME, workspace=_WORKSPACE_NAME,
        status="closed", disposition="resolved")

    _, body = client.put.call_args[0]
    assert body == {"status": "closed", "disposition": "resolved"}


@pytest.mark.unit
def test_close_defaults_to_resolved(mocker):
    ticket, _, _ = _make_ticket(mocker)
    client = _make_client(mocker, ticket)
    put_mock = mocker.MagicMock()
    put_mock.json.return_value = {"name": _TICKET_NAME, "status": "closed"}
    client.put.return_value = put_mock

    # disposition=None mirrors the CLI (argparse default), and must still
    # resolve to "resolved" — the backend rejects a close with no disposition.
    ticket.close(name=_TICKET_NAME, workspace=_WORKSPACE_NAME, disposition=None)

    url, body = client.put.call_args[0]
    assert url.endswith("/status")
    assert body == {"status": "closed", "disposition": "resolved"}


@pytest.mark.unit
def test_delete(mocker):
    ticket, wksp_svc, _ = _make_ticket(mocker)
    client = _make_client(mocker, ticket)

    result = ticket.delete(name=_TICKET_NAME, workspace=_WORKSPACE_NAME)

    wksp_svc.find.assert_called_once()
    client.delete.assert_called_once()
    assert client.delete.call_args[0][0].endswith(
        f"/tickets/{_WORKSPACE_ID}/{_TICKET_NAME}")
    assert "deleted" in result["message"]


@pytest.mark.unit
def test_delete_requires_identifier(mocker):
    ticket, _, _ = _make_ticket(mocker)
    _make_client(mocker, ticket)

    with pytest.raises(DuploError, match="name or --id"):
        ticket.delete(workspace=_WORKSPACE_NAME)
