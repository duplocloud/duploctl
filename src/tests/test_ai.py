import pytest
from duplocloud.errors import DuploError
from duplo_resource.ai import DuploAI
from .conftest import get_test_data

@pytest.fixture(scope="class")
def helpdesk_resource(duplo, request):
    """Fixture to load the AI Helpdesk resource and test data."""
    resource = duplo.load("ai")
    request.cls.ticket_data = get_test_data("ticket")
    return resource

def execute_test(func, *args, **kwargs):
    """Helper to execute a test and capture DuploError cleanly."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")


_WORKSPACE_ID = "6a0db3da984d2b398701bca7"
_WORKSPACE_NAME = "platform"
_AGENT_ID = "agent-abc-123"


def _make_ai(mocker):
    """Create a DuploAI instance with a mocked duplo client."""
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = False
    mock_duplo.host = "https://example.duplocloud.net"
    mock_duplo.timeout = 30
    ai = DuploAI(mock_duplo)
    ai._tenant = {"AccountName": "myaccount", "TenantId": "tid-123"}
    ai._tenant_id = "tid-123"
    return ai


def _make_client(mocker, ai, get_responses, post_responses):
    """Wire a mock client onto `ai` returning the supplied GET/POST JSON payloads in order."""
    mock_client = mocker.MagicMock()
    mock_client.token = "fake-token"

    get_mocks = [mocker.MagicMock() for _ in get_responses]
    for m, payload in zip(get_mocks, get_responses):
        m.json.return_value = payload
    mock_client.get.side_effect = get_mocks

    post_mocks = [mocker.MagicMock() for _ in post_responses]
    for m, payload in zip(post_mocks, post_responses):
        m.json.return_value = payload
    mock_client.post.side_effect = post_mocks

    mocker.patch.object(ai, "client", mock_client)
    return mock_client


_WORKSPACE_LIST_RESPONSE = {
    "success": True,
    "data": {
        "items": [{"id": _WORKSPACE_ID, "name": _WORKSPACE_NAME}],
    },
}

_AGENT_LIST_RESPONSE = {
    "success": True,
    "data": {
        "items": [{"id": _AGENT_ID, "name": "cicd"}],
    },
}

_AGENT_DETAIL_NON_STREAMING = {
    "success": True,
    "data": {
        "id": _AGENT_ID,
        "name": "cicd",
        "doesSupportStreaming": False,
        "metaData": {"STREAMING_ENABLED": "false"},
    },
}

_AGENT_DETAIL_STREAMING = {
    "success": True,
    "data": {
        "id": _AGENT_ID,
        "name": "cicd",
        "doesSupportStreaming": False,  # top-level lies, metaData is the source of truth
        "metaData": {"STREAMING_ENABLED": "true"},
    },
}

_TICKET_RESPONSE = {"success": True, "data": {"name": "DEVOPS-42", "id": "ticket-id-1"}}

_TICKET_DETAIL = {
    "success": True,
    "data": {
        "name": "DEVOPS-42",
        "id": "ticket-id-1",
        "aiAgentId": _AGENT_ID,
        "workspaceId": _WORKSPACE_ID,
    },
}


@pytest.mark.unit
def test_create_ticket_with_agent_id_skips_agent_lookup(mocker):
    """When agent_id is provided (no content), only the workspaces GET runs."""
    ai = _make_ai(mocker)
    client = _make_client(mocker, ai,
                          get_responses=[_WORKSPACE_LIST_RESPONSE],
                          post_responses=[_TICKET_RESPONSE])

    result = ai.create_ticket(
        title="Test ticket",
        workspace_name=_WORKSPACE_NAME,
        agent_id="agent-direct-999",
    )

    assert client.get.call_count == 1
    assert "workspaces" in client.get.call_args_list[0][0][0]

    post_url, post_body = client.post.call_args[0]
    assert post_url.endswith(f"/tickets/{_WORKSPACE_ID}")
    assert post_body.get("aiAgentId") == "agent-direct-999"
    assert post_body.get("workspaceId") == _WORKSPACE_ID
    assert post_body.get("source") == "helpdesk"
    assert "assignee" not in post_body

    assert result["ticketname"] == "DEVOPS-42"
    assert result["chat_url"].endswith(f"/{_WORKSPACE_ID}/tickets/chat/DEVOPS-42")
    assert result["ai_response"] is None


@pytest.mark.unit
def test_create_ticket_with_agent_id_preferred_over_name(mocker):
    """When both agent_id and agent_name are given (no content), agent_id wins and no agents GET runs."""
    ai = _make_ai(mocker)
    client = _make_client(mocker, ai,
                          get_responses=[_WORKSPACE_LIST_RESPONSE],
                          post_responses=[_TICKET_RESPONSE])

    ai.create_ticket(
        title="Test",
        workspace_name=_WORKSPACE_NAME,
        agent_id="agent-direct-999",
        agent_name="cicd",
    )

    assert client.get.call_count == 1
    assert client.post.call_args[0][1].get("aiAgentId") == "agent-direct-999"


@pytest.mark.unit
def test_create_ticket_with_agent_name_runs_both_lookups(mocker):
    """When only agent_name is given (no content), both workspaces and agents GETs run."""
    ai = _make_ai(mocker)
    client = _make_client(mocker, ai,
                          get_responses=[_WORKSPACE_LIST_RESPONSE, _AGENT_LIST_RESPONSE],
                          post_responses=[_TICKET_RESPONSE])

    result = ai.create_ticket(
        title="Test ticket",
        workspace_name=_WORKSPACE_NAME,
        agent_name="cicd",
    )

    assert client.get.call_count == 2
    urls = [call[0][0] for call in client.get.call_args_list]
    assert any("workspaces" in u for u in urls)
    assert any("aiagents" in u for u in urls)

    post_body = client.post.call_args[0][1]
    assert post_body.get("aiAgentId") == _AGENT_ID
    assert result["chat_url"].endswith(f"/{_WORKSPACE_ID}/tickets/chat/DEVOPS-42")


@pytest.mark.unit
def test_create_ticket_workspace_name_case_insensitive(mocker):
    """User can pass 'DEVOPS' even when the stored name is 'Devops' — match is case-insensitive."""
    ai = _make_ai(mocker)
    api_response = {
        "success": True,
        "data": {"items": [{"id": _WORKSPACE_ID, "name": "Devops"}]},
    }
    client = _make_client(mocker, ai,
                          get_responses=[api_response],
                          post_responses=[_TICKET_RESPONSE])

    result = ai.create_ticket(title="Test", workspace_name="DEVOPS", agent_id=_AGENT_ID)

    post_url = client.post.call_args[0][0]
    assert post_url.endswith(f"/tickets/{_WORKSPACE_ID}")
    assert result["ticketname"] == "DEVOPS-42"


@pytest.mark.unit
def test_create_ticket_unknown_workspace_raises(mocker):
    """Zero workspace matches → clear error, no POST attempted."""
    ai = _make_ai(mocker)
    client = _make_client(mocker, ai,
                          get_responses=[{"success": True, "data": {"items": []}}],
                          post_responses=[])

    with pytest.raises(DuploError, match="No AI HelpDesk workspace found"):
        ai.create_ticket(title="Test", workspace_name="missing", agent_id="x")

    assert client.post.call_count == 0


@pytest.mark.unit
def test_create_ticket_ambiguous_workspace_raises(mocker):
    """Multiple workspace matches → clear error telling user to disambiguate."""
    ai = _make_ai(mocker)
    multi = {"success": True, "data": {"items": [
        {"id": "ws-1", "name": _WORKSPACE_NAME},
        {"id": "ws-2", "name": _WORKSPACE_NAME},
    ]}}
    client = _make_client(mocker, ai,
                          get_responses=[multi],
                          post_responses=[])

    with pytest.raises(DuploError, match="Multiple AI HelpDesk workspaces"):
        ai.create_ticket(title="Test", workspace_name=_WORKSPACE_NAME, agent_id="x")

    assert client.post.call_count == 0


@pytest.mark.unit
def test_create_ticket_unknown_agent_raises(mocker):
    """Workspace resolves, but agent_name lookup empty → DuploError."""
    ai = _make_ai(mocker)
    _make_client(mocker, ai,
                 get_responses=[_WORKSPACE_LIST_RESPONSE, {"success": True, "data": {"items": []}}],
                 post_responses=[])

    with pytest.raises(DuploError, match="No AI agent found"):
        ai.create_ticket(title="Test", workspace_name=_WORKSPACE_NAME, agent_name="unknown")


@pytest.mark.unit
def test_create_ticket_ambiguous_agent_raises(mocker):
    """Multiple agent matches → clear error telling user to disambiguate."""
    ai = _make_ai(mocker)
    multi = {"success": True, "data": {"items": [
        {"id": "agent-1", "name": "cicd"},
        {"id": "agent-2", "name": "cicd"},
    ]}}
    client = _make_client(mocker, ai,
                          get_responses=[_WORKSPACE_LIST_RESPONSE, multi],
                          post_responses=[])

    with pytest.raises(DuploError, match="Multiple AI agents"):
        ai.create_ticket(title="Test", workspace_name=_WORKSPACE_NAME, agent_name="cicd")

    assert client.post.call_count == 0


@pytest.mark.unit
def test_resolve_workspace_id_url_encodes_name(mocker):
    """Names with spaces/special chars are URL-encoded in the lookup query."""
    ai = _make_ai(mocker)
    api_response = {
        "success": True,
        "data": {"items": [{"id": _WORKSPACE_ID, "name": "my workspace"}]},
    }
    client = _make_client(mocker, ai,
                          get_responses=[api_response],
                          post_responses=[_TICKET_RESPONSE])

    ai.create_ticket(title="Test", workspace_name="my workspace", agent_id=_AGENT_ID)

    workspace_get_url = client.get.call_args_list[0][0][0]
    assert "filters[name]=my+workspace" in workspace_get_url


@pytest.mark.unit
def test_resolve_workspace_id_raises_when_id_missing(mocker):
    """A matched workspace record without an 'id' field surfaces a clear error."""
    ai = _make_ai(mocker)
    api_response = {
        "success": True,
        "data": {"items": [{"name": _WORKSPACE_NAME}]},  # no 'id'
    }
    _make_client(mocker, ai,
                 get_responses=[api_response],
                 post_responses=[])

    with pytest.raises(DuploError, match="missing an 'id' field"):
        ai.create_ticket(title="Test", workspace_name=_WORKSPACE_NAME, agent_id="x")


@pytest.mark.unit
def test_create_ticket_requires_agent_id_or_name(mocker):
    """Workspace given but no agent → DuploError, no POST attempted."""
    ai = _make_ai(mocker)
    client = _make_client(mocker, ai,
                          get_responses=[_WORKSPACE_LIST_RESPONSE],
                          post_responses=[])

    with pytest.raises(DuploError, match="Either --agent_id or --agent_name is required"):
        ai.create_ticket(title="Test", workspace_name=_WORKSPACE_NAME)

    assert client.post.call_count == 0


@pytest.mark.unit
def test_create_ticket_with_content_uses_non_streaming_when_flag_false(mocker):
    """STREAMING_ENABLED='false' → unary POST /sendMessage."""
    ai = _make_ai(mocker)
    client = _make_client(
        mocker, ai,
        get_responses=[_WORKSPACE_LIST_RESPONSE, _AGENT_DETAIL_NON_STREAMING],
        post_responses=[
            _TICKET_RESPONSE,
            {"content": "Agent reply here", "role": "assistant"},
        ],
    )

    result = ai.create_ticket(
        title="Test ticket",
        workspace_name=_WORKSPACE_NAME,
        agent_id=_AGENT_ID,
        content="Hello agent",
    )

    assert client.post.call_count == 2
    second_post_url = client.post.call_args_list[1][0][0]
    assert second_post_url == f"v1/aiservicedesk/tickets/{_WORKSPACE_ID}/DEVOPS-42/sendMessage"
    assert result["ai_response"] == "Agent reply here"


@pytest.mark.unit
def test_create_ticket_default_origin(mocker):
    """Origin defaults to 'duploctl' when not specified."""
    ai = _make_ai(mocker)
    client = _make_client(mocker, ai,
                          get_responses=[_WORKSPACE_LIST_RESPONSE],
                          post_responses=[_TICKET_RESPONSE])

    ai.create_ticket(title="Test", workspace_name=_WORKSPACE_NAME, agent_id=_AGENT_ID)

    assert client.post.call_args[0][1].get("Origin") == "duploctl"


@pytest.mark.unit
def test_create_ticket_custom_origin(mocker):
    """Origin is forwarded when explicitly provided."""
    ai = _make_ai(mocker)
    client = _make_client(mocker, ai,
                          get_responses=[_WORKSPACE_LIST_RESPONSE],
                          post_responses=[_TICKET_RESPONSE])

    ai.create_ticket(
        title="Test",
        workspace_name=_WORKSPACE_NAME,
        agent_id=_AGENT_ID,
        helpdesk_origin="pipelines",
    )

    assert client.post.call_args[0][1].get("Origin") == "pipelines"


@pytest.mark.unit
def test_send_message_standalone_non_streaming(mocker):
    """send_message standalone: GET workspaces → GET ticket → GET agent → POST sendMessage."""
    ai = _make_ai(mocker)
    client = _make_client(
        mocker, ai,
        get_responses=[_WORKSPACE_LIST_RESPONSE, _TICKET_DETAIL, _AGENT_DETAIL_NON_STREAMING],
        post_responses=[{"content": "ack", "role": "assistant"}],
    )

    result = ai.send_message(
        workspace_name=_WORKSPACE_NAME,
        ticket_id="DEVOPS-42",
        content="hello",
    )

    post_url = client.post.call_args[0][0]
    assert post_url == f"v1/aiservicedesk/tickets/{_WORKSPACE_ID}/DEVOPS-42/sendMessage"
    assert result["chat_url"].endswith(f"/{_WORKSPACE_ID}/tickets/chat/DEVOPS-42")
    assert result["ai_response"]["content"] == "ack"


def _fake_sse_response(mocker, sse_lines):
    """Build a context-managed mock streaming response yielding the given SSE lines."""
    fake_stream = mocker.MagicMock()
    fake_stream.iter_lines.return_value = iter(sse_lines)
    fake_stream.__enter__ = mocker.MagicMock(return_value=fake_stream)
    fake_stream.__exit__ = mocker.MagicMock(return_value=False)
    return fake_stream


@pytest.mark.unit
def test_create_ticket_with_content_uses_streaming_when_flag_true(mocker):
    """STREAMING_ENABLED='true' → POST routed via client.stream_post + SSE parse."""
    ai = _make_ai(mocker)
    client = _make_client(
        mocker, ai,
        get_responses=[_WORKSPACE_LIST_RESPONSE, _AGENT_DETAIL_STREAMING],
        post_responses=[_TICKET_RESPONSE],
    )

    sse_lines = [
        'event: message',
        'data: {"type":"text_delta","text":"Hello "}',
        '',
        'event: message',
        'data: {"type":"text_delta","text":"world"}',
        '',
        'event: message',
        'data: {"type":"done","stop_reason":"end_turn"}',
        '',
    ]
    client.stream_post.return_value = _fake_sse_response(mocker, sse_lines)

    result = ai.create_ticket(
        title="Test ticket",
        workspace_name=_WORKSPACE_NAME,
        agent_id=_AGENT_ID,
        content="Hello agent",
    )

    # The non-streaming sendMessage POST should NOT have been used
    assert client.post.call_count == 1
    assert client.post.call_args_list[0][0][0].endswith(f"/tickets/{_WORKSPACE_ID}")

    client.stream_post.assert_called_once()
    streaming_path = client.stream_post.call_args[0][0]
    assert streaming_path == (
        f"v1/aiservicedesk/tickets/{_WORKSPACE_ID}/DEVOPS-42/sendMessageStreaming"
    )
    extra_headers = client.stream_post.call_args[1]["extra_headers"]
    assert extra_headers == {"Accept": "text/event-stream"}

    assert result["ai_response"] == "Hello world"


@pytest.mark.unit
def test_streaming_sse_handles_error_event(mocker):
    """An `error` SSE event surfaces as DuploError."""
    ai = _make_ai(mocker)
    client = _make_client(
        mocker, ai,
        get_responses=[_WORKSPACE_LIST_RESPONSE, _TICKET_DETAIL, _AGENT_DETAIL_STREAMING],
        post_responses=[],
    )

    sse_lines = [
        'event: error',
        'data: {"type":"error","error":"agent exploded"}',
        '',
    ]
    client.stream_post.return_value = _fake_sse_response(mocker, sse_lines)

    with pytest.raises(DuploError, match="agent exploded"):
        ai.send_message(
            workspace_name=_WORKSPACE_NAME,
            ticket_id="DEVOPS-42",
            content="hello",
        )

    # client.post never called — streaming path uses client.stream_post
    assert client.post.call_count == 0


@pytest.mark.unit
def test_streaming_sse_propagates_http_error(mocker):
    """Non-2xx status on the streaming POST raises DuploError via the shared client."""
    ai = _make_ai(mocker)
    client = _make_client(
        mocker, ai,
        get_responses=[_WORKSPACE_LIST_RESPONSE, _TICKET_DETAIL, _AGENT_DETAIL_STREAMING],
        post_responses=[],
    )

    # The shared client raises before returning when status is non-2xx —
    # _validate_response wraps it as DuploError. Simulate that behavior.
    client.stream_post.side_effect = DuploError(
        "Duplo responded with (500): boom", 500
    )

    with pytest.raises(DuploError, match="500"):
        ai.send_message(
            workspace_name=_WORKSPACE_NAME,
            ticket_id="DEVOPS-42",
            content="hello",
        )


@pytest.mark.integration
@pytest.mark.usefixtures("helpdesk_resource")
class TestDuploAI:
    """Integration tests for the AI Helpdesk ticketing system."""

    @pytest.mark.dependency(name="create_ticket", depends=["find_tenant_resource"], scope="session")
    @pytest.mark.order(120)
    def test_create_ticket(self, helpdesk_resource):
        """Test creating a helpdesk ticket."""
        response = execute_test(
            helpdesk_resource.create_ticket,
            title=self.ticket_data["title"],
            workspace_name=self.ticket_data["workspace_name"],
            content=self.ticket_data["message"],
            agent_name=self.ticket_data["agent_name"],
            api_version=self.ticket_data.get("api_version", "v1")
        )

        assert isinstance(response, dict)
        assert "ticketname" in response
        assert response["ticketname"]
        assert "chat_url" in response
        assert response["chat_url"].endswith(response["ticketname"])
        assert "ai_response" in response
        assert isinstance(response["ai_response"], str)

        # Save ticket ID for next test
        self.__class__.ticket_id = response["ticketname"]

    @pytest.mark.dependency(depends=["create_ticket"], scope="session")
    @pytest.mark.order(121)
    def test_create_ticket_with_origin(self, helpdesk_resource):
        """Test creating a helpdesk ticket with origin parameter."""
        response = execute_test(
            helpdesk_resource.create_ticket,
            title="Pipeline ticket with origin",
            workspace_name=self.ticket_data["workspace_name"],
            content="This ticket was created from a pipeline",
            agent_name=self.ticket_data["agent_name"],
            helpdesk_origin="pipelines",
            api_version=self.ticket_data.get("api_version", "v1")
        )

        assert isinstance(response, dict)
        assert "ticketname" in response
        assert response["ticketname"]
        assert "chat_url" in response
        assert response["chat_url"].endswith(response["ticketname"])
        assert "ai_response" in response

    @pytest.mark.dependency(depends=["create_ticket"], scope="session")
    @pytest.mark.order(121)
    def test_create_ticket_with_default_origin(self, helpdesk_resource):
        """Test creating a helpdesk ticket without origin parameter (should default to 'duploctl')."""
        response = execute_test(
            helpdesk_resource.create_ticket,
            title="Default origin ticket",
            workspace_name=self.ticket_data["workspace_name"],
            content="This ticket should use default origin",
            agent_name=self.ticket_data["agent_name"],
            api_version=self.ticket_data.get("api_version", "v1")
        )

        assert isinstance(response, dict)
        assert "ticketname" in response
        assert response["ticketname"]
        assert "chat_url" in response
        assert response["chat_url"].endswith(response["ticketname"])
        assert "ai_response" in response

    @pytest.mark.dependency(depends=["create_ticket"], scope="session")
    @pytest.mark.order(122)
    def test_send_message(self, helpdesk_resource):
        """Test sending a message to an existing ticket."""
        assert hasattr(self, "ticket_id"), "Ticket ID must be created before sending a message."

        response = execute_test(
            helpdesk_resource.send_message,
            workspace_name=self.ticket_data["workspace_name"],
            ticket_id=self.ticket_id,
            content=self.ticket_data.get("followup_message", "This is a test message."),
            api_version=self.ticket_data.get("api_version", "v1")
        )

        assert isinstance(response, dict)
        assert "ai_response" in response
        assert "chat_url" in response
        assert self.ticket_id in response["chat_url"]
