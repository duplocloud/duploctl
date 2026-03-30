import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from duplocloud.errors import DuploError
from .conftest import get_test_data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


@pytest.fixture
def mock_ai():
    """Create a mock DuploAI resource with a fake HTTP client."""
    from duplo_resource.ai import DuploAI
    mock_duplo = MagicMock()
    mock_duplo.host = "https://test.duplocloud.net"
    mock_duplo.token = "fake-token"
    mock_duplo.output = None
    mock_client = MagicMock()
    mock_duplo.load_client.return_value = mock_client

    ai = DuploAI.__new__(DuploAI)
    ai.duplo = mock_duplo
    ai.client = mock_client
    ai._slug = ""
    ai._tenant = None
    ai._tenant_id = "abc123def456789012345678"
    return ai, mock_client


# ---------------------------------------------------------------------------
# Unit tests — list_workspaces
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestListWorkspaces:
    """Unit tests for list_workspaces command."""

    def test_returns_workspace_list(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = {
            "success": True,
            "data": {
                "items": [
                    {"id": "ws1", "name": "Engineering"},
                    {"id": "ws2", "name": "Platform"},
                ]
            }
        }
        client.get.return_value = response

        result = ai.list_workspaces()
        client.get.assert_called_once_with(
            "v1/aiservicedesk/admin/data/workspaces"
        )
        assert result == response.json.return_value

    def test_empty_workspaces(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = {
            "success": True,
            "data": {"items": []}
        }
        client.get.return_value = response

        result = ai.list_workspaces()
        assert result["data"]["items"] == []


# ---------------------------------------------------------------------------
# Unit tests — list_projects
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestListProjects:
    """Unit tests for list_projects command."""

    def test_returns_project_list(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = {
            "success": True,
            "data": {
                "items": [
                    {"id": "p1", "name": "Auth Rewrite"},
                    {"id": "p2", "name": "Dashboard v2"},
                ]
            }
        }
        client.get.return_value = response

        result = ai.list_projects()
        expected_path = (
            "v1/aiservicedesk/user/data/projects"
            "?filters[workspaceId]=abc123def456789012345678"
        )
        client.get.assert_called_once_with(expected_path)
        assert len(result["data"]["items"]) == 2

    def test_empty_projects(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = {
            "success": True,
            "data": {"items": []}
        }
        client.get.return_value = response

        result = ai.list_projects()
        assert result["data"]["items"] == []


# ---------------------------------------------------------------------------
# Unit tests — get_project
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetProject:
    """Unit tests for get_project command."""

    def test_returns_project_details(self, mock_ai):
        ai, client = mock_ai
        project_data = {
            "id": "p1",
            "name": "Auth Rewrite",
            "spec": {
                "content": "# Spec content",
                "metaData": {"approvalState": "Approved"}
            },
            "plan": {
                "content": "# Plan content",
                "metaData": {"approvalState": "Draft"}
            },
            "executionTasks": [{"id": "t1", "title": "Task 1"}],
            "scopeIds": ["s1", "s2"],
        }
        response = MagicMock()
        response.json.return_value = project_data
        client.get.return_value = response

        result = ai.get_project(project_id="p1")
        client.get.assert_called_once_with(
            "v1/aiservicedesk/user/data/projects/p1"
        )
        assert result["spec"]["content"] == "# Spec content"
        assert result["plan"]["metaData"]["approvalState"] == "Draft"

    def test_project_not_found(self, mock_ai):
        ai, client = mock_ai
        client.get.side_effect = DuploError("Not found", 404)

        with pytest.raises(DuploError):
            ai.get_project(project_id="nonexistent")


# ---------------------------------------------------------------------------
# Unit tests — save_spec
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSaveSpec:
    """Unit tests for save_spec command."""

    def test_saves_spec_content(self, mock_ai):
        ai, client = mock_ai
        existing = {
            "id": "p1",
            "name": "Project",
            "spec": {"content": "", "metaData": {}},
            "plan": {"content": ""},
        }
        get_response = MagicMock()
        get_response.json.return_value = existing
        put_response = MagicMock()
        client.get.return_value = get_response
        client.put.return_value = put_response

        result = ai.save_spec(
            project_id="p1",
            artifact_content="# New spec"
        )

        put_call = client.put.call_args
        assert put_call[0][0] == "v1/aiservicedesk/user/data/projects/p1"
        saved = put_call[0][1]
        assert saved["spec"]["content"] == "# New spec"
        assert result["message"] == "Spec saved"

    def test_saves_and_approves_spec(self, mock_ai):
        ai, client = mock_ai
        existing = {
            "id": "p1",
            "spec": {"content": "", "metaData": {}},
            "plan": {},
        }
        get_response = MagicMock()
        get_response.json.return_value = existing
        client.get.return_value = get_response
        client.put.return_value = MagicMock()

        result = ai.save_spec(
            project_id="p1",
            artifact_content="# Approved spec",
            approve=True,
        )

        saved = client.put.call_args[0][1]
        assert saved["spec"]["content"] == "# Approved spec"
        assert saved["spec"]["metaData"]["approvalState"] == "Approved"
        assert result["message"] == "Spec saved and approved"


# ---------------------------------------------------------------------------
# Unit tests — save_plan
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSavePlan:
    """Unit tests for save_plan command."""

    def test_saves_plan_content(self, mock_ai):
        ai, client = mock_ai
        existing = {
            "id": "p1",
            "spec": {},
            "plan": {"content": "", "metaData": {}},
        }
        get_response = MagicMock()
        get_response.json.return_value = existing
        client.get.return_value = get_response
        client.put.return_value = MagicMock()

        result = ai.save_plan(
            project_id="p1",
            artifact_content="# Implementation plan"
        )

        saved = client.put.call_args[0][1]
        assert saved["plan"]["content"] == "# Implementation plan"
        assert result["message"] == "Plan saved"

    def test_saves_and_approves_plan(self, mock_ai):
        ai, client = mock_ai
        existing = {
            "id": "p1",
            "spec": {},
            "plan": {"content": "", "metaData": {}},
        }
        get_response = MagicMock()
        get_response.json.return_value = existing
        client.get.return_value = get_response
        client.put.return_value = MagicMock()

        result = ai.save_plan(
            project_id="p1",
            artifact_content="# Approved plan",
            approve=True,
        )

        saved = client.put.call_args[0][1]
        assert saved["plan"]["metaData"]["approvalState"] == "Approved"
        assert result["message"] == "Plan saved and approved"


# ---------------------------------------------------------------------------
# Unit tests — list_agents
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestListAgents:
    """Unit tests for list_agents command."""

    def test_returns_agent_list(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = [
            {"id": "a1", "name": "cicd-agent"},
            {"id": "a2", "name": "devops-agent"},
        ]
        client.get.return_value = response

        result = ai.list_agents()
        expected = (
            "v1/aiservicedesk/user/data"
            "/workspaces/abc123def456789012345678/agents"
        )
        client.get.assert_called_once_with(expected)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Unit tests — list_tickets
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestListTickets:
    """Unit tests for list_tickets command."""

    def test_lists_spec_tickets(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = [
            {"id": "t1", "name": "spec-ticket-1", "title": "Spec Ticket"},
        ]
        client.get.return_value = response

        result = ai.list_tickets(
            project_id="p1",
            ticket_type="spec_creation",
        )
        path = client.get.call_args[0][0]
        assert "projectType=0" in path
        assert "projectId=p1" in path

    def test_lists_execution_tickets(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = []
        client.get.return_value = response

        result = ai.list_tickets(
            project_id="p1",
            ticket_type="plan_execution",
        )
        path = client.get.call_args[0][0]
        assert "projectType=2" in path


# ---------------------------------------------------------------------------
# Unit tests — get_ticket
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetTicket:
    """Unit tests for get_ticket command."""

    def test_gets_ticket_by_name(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = {
            "id": "t1",
            "name": "my-ticket-250320",
            "title": "My Ticket",
        }
        client.get.return_value = response

        result = ai.get_ticket(ticket_ref="my-ticket-250320")
        expected = (
            "v1/aiservicedesk/tickets"
            "/abc123def456789012345678/my-ticket-250320"
        )
        client.get.assert_called_once_with(expected)
        assert result["name"] == "my-ticket-250320"


# ---------------------------------------------------------------------------
# Unit tests — create_project_ticket
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCreateProjectTicket:
    """Unit tests for create_project_ticket command."""

    def test_creates_spec_ticket(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = {
            "id": "t1",
            "name": "proj-Spec-Creation-Ticket",
            "title": "MyProject-Spec-Creation-Ticket",
        }
        client.post.return_value = response

        result = ai.create_project_ticket(
            project_id="p1",
            agent_id="a1",
            ticket_type="spec_creation",
            project_name="MyProject",
        )

        payload = client.post.call_args[0][1]
        assert payload["title"] == "MyProject-Spec-Creation-Ticket"
        assert payload["aiAgentId"] == "a1"
        assert payload["project"]["id"] == "p1"
        assert payload["project"]["type"] == 0

    def test_creates_execution_ticket(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = {"id": "t2", "name": "exec-ticket"}
        client.post.return_value = response

        result = ai.create_project_ticket(
            project_id="p1",
            agent_id="a1",
            ticket_type="plan_execution",
        )

        payload = client.post.call_args[0][1]
        assert payload["project"]["type"] == 2
        assert "Plan-Execution-Ticket" in payload["title"]


# ---------------------------------------------------------------------------
# Unit tests — mirror_message
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMirrorMessage:
    """Unit tests for mirror_message command."""

    def test_mirrors_user_message(self, mock_ai):
        ai, client = mock_ai
        client.post.return_value = MagicMock()

        result = ai.mirror_message(
            ticket_name="my-ticket-250320",
            content="User said something",
            role="user",
        )

        path = client.post.call_args[0][0]
        assert "/sendmessageStreaming" in path
        payload = client.post.call_args[0][1]
        assert payload["role"] == "user"
        assert payload["content"] == "User said something"
        assert result["message"] == "Message mirrored"

    def test_mirrors_assistant_message(self, mock_ai):
        ai, client = mock_ai
        client.post.return_value = MagicMock()

        result = ai.mirror_message(
            ticket_name="my-ticket",
            content="Claude responded",
            role="assistant",
        )

        payload = client.post.call_args[0][1]
        assert payload["role"] == "assistant"
        assert result["role"] == "assistant"

    def test_rejects_empty_content(self, mock_ai):
        ai, _ = mock_ai

        with pytest.raises(ValueError):
            ai.mirror_message(
                ticket_name="my-ticket",
                content="",
            )

    def test_rejects_whitespace_content(self, mock_ai):
        ai, _ = mock_ai

        with pytest.raises(ValueError):
            ai.mirror_message(
                ticket_name="my-ticket",
                content="   ",
            )


# ---------------------------------------------------------------------------
# Unit tests — send_message
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSendMessage:
    """Unit tests for send_message command."""

    def test_sends_message(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = {"content": "AI response"}
        client.post.return_value = response

        result = ai.send_message(
            ticket_id="my-ticket-250320",
            content="Hello agent",
        )

        path = client.post.call_args[0][0]
        assert "/sendmessage" in path
        assert "sendmessageStreaming" not in path
        assert "ai_response" in result
        assert "chat_url" in result

    def test_handles_streaming_500_error(self, mock_ai):
        ai, client = mock_ai
        error_msg = (
            'Duplo responded with (500): "'
            '{"type":"text_delta","text":"Hello"}\n'
            '{"type":"text_delta","text":" World"}\n'
            '{"type":"done"}\n"'
        )
        client.post.side_effect = DuploError(error_msg, 500)

        result = ai.send_message(
            ticket_id="t1",
            content="Test",
        )

        assert result["ai_response"] == "Hello World"
        assert "chat_url" in result

    def test_rejects_empty_content(self, mock_ai):
        ai, _ = mock_ai
        with pytest.raises(ValueError):
            ai.send_message(ticket_id="t1", content="")


# ---------------------------------------------------------------------------
# Unit tests — create_ticket
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCreateTicket:
    """Unit tests for create_ticket command."""

    def test_creates_ticket_without_content(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = {
            "ticket": {"name": "shantanu-250320123456"},
            "message": None,
        }
        client.post.return_value = response

        result = ai.create_ticket(
            title="Test ticket",
            agent_name="cicd",
            instance_id="cicd",
        )

        assert result["ticketname"] == "shantanu-250320123456"
        assert "chat_url" in result
        assert result["ai_response"] is None
        payload = client.post.call_args[0][1]
        assert payload["title"] == "Test ticket"
        assert payload["aiAgentId"] == "cicd"
        assert payload["Origin"] == "duploctl"
        # No content, so post should be called only once (create only)
        assert client.post.call_count == 1

    def test_creates_ticket_with_content_sends_message(self, mock_ai):
        ai, client = mock_ai
        # First call: create ticket, second call: send message
        create_resp = MagicMock()
        create_resp.json.return_value = {
            "ticket": {"name": "t1"},
            "message": None,
        }
        send_resp = MagicMock()
        send_resp.json.return_value = {"content": "AI says hello"}
        client.post.side_effect = [create_resp, send_resp]

        result = ai.create_ticket(
            title="Test",
            agent_name="cicd",
            instance_id="cicd",
            content="Build failed",
        )

        assert result["ticketname"] == "t1"
        # post called twice: create + send_message
        assert client.post.call_count == 2

    def test_creates_ticket_with_origin(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = {
            "ticket": {"name": "t1"},
            "message": None,
        }
        client.post.return_value = response

        ai.create_ticket(
            title="Pipeline ticket",
            agent_name="cicd",
            instance_id="cicd",
            helpdesk_origin="pipelines",
        )

        payload = client.post.call_args[0][1]
        assert payload["Origin"] == "pipelines"

    def test_raises_on_null_ticket_name(self, mock_ai):
        ai, client = mock_ai
        response = MagicMock()
        response.json.return_value = {
            "ticket": {"name": "null"},
            "message": None,
        }
        response.text = '{"ticket": {"name": "null"}}'
        client.post.return_value = response

        with pytest.raises(DuploError):
            ai.create_ticket(
                title="Bad ticket",
                agent_name="agent",
                instance_id="inst",
            )


@pytest.mark.unit
class TestParseStreamingError:
    """Unit tests for _parse_streaming_error."""

    def test_extracts_text_from_ndjson_error(self):
        from duplo_resource.ai import DuploAI
        error = (
            'Duplo responded with (500): "Error '
            '\\u0022type\\u0022:\\u0022text_delta\\u0022,'
            '\\u0022text\\u0022:\\u0022Hello\\u0022}\\n'
            '{\\u0022type\\u0022:\\u0022text_delta\\u0022,'
            '\\u0022text\\u0022:\\u0022 World\\u0022}\\n'
            '{\\u0022type\\u0022:\\u0022done\\u0022}"'
        )
        # The unicode escapes in the string literal mean the actual string
        # contains \u0022 as literal text (not decoded to ")
        # Since _parse_streaming_error uses unicode_escape decoding,
        # test with a simulated real error
        real_error = (
            'Duplo responded with (500): "Error '
            '{"type":"text_delta","text":"Hello"}\n'
            '{"type":"text_delta","text":" World"}\n'
            '{"type":"done","stop_reason":"end_turn"}\n"'
        )
        result = DuploAI._parse_streaming_error(real_error)
        assert result == "Hello World"

    def test_returns_raw_on_no_json(self):
        from duplo_resource.ai import DuploAI
        result = DuploAI._parse_streaming_error("some random error")
        assert result == "some random error"


# ---------------------------------------------------------------------------
# Integration tests (require live credentials)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.usefixtures("helpdesk_resource")
class TestDuploAIIntegration:
    """Integration tests for the AI Helpdesk ticketing system."""

    @pytest.mark.dependency(
        name="create_ticket",
        depends=["find_tenant_resource"],
        scope="session",
    )
    @pytest.mark.order(120)
    def test_create_ticket(self, helpdesk_resource):
        """Test creating a helpdesk ticket."""
        response = execute_test(
            helpdesk_resource.create_ticket,
            title=self.ticket_data["title"],
            content=self.ticket_data["message"],
            agent_name=self.ticket_data["agent_name"],
            instance_id=self.ticket_data["instance_id"],
            api_version=self.ticket_data.get("api_version", "v1"),
        )

        assert isinstance(response, dict)
        assert "ticketname" in response
        assert response["ticketname"]
        assert "chat_url" in response
        assert response["chat_url"].endswith(response["ticketname"])
        assert "ai_response" in response
        assert isinstance(response["ai_response"], str)

        self.__class__.ticket_id = response["ticketname"]

    @pytest.mark.dependency(depends=["create_ticket"], scope="session")
    @pytest.mark.order(121)
    def test_create_ticket_with_origin(self, helpdesk_resource):
        """Test creating a helpdesk ticket with origin parameter."""
        response = execute_test(
            helpdesk_resource.create_ticket,
            title="Pipeline ticket with origin",
            content="This ticket was created from a pipeline",
            agent_name=self.ticket_data["agent_name"],
            instance_id=self.ticket_data["instance_id"],
            helpdesk_origin="pipelines",
            api_version=self.ticket_data.get("api_version", "v1"),
        )

        assert isinstance(response, dict)
        assert "ticketname" in response
        assert response["ticketname"]
        assert "chat_url" in response
        assert "ai_response" in response

    @pytest.mark.dependency(depends=["create_ticket"], scope="session")
    @pytest.mark.order(121)
    def test_create_ticket_with_default_origin(self, helpdesk_resource):
        """Test creating a ticket without origin defaults to duploctl."""
        response = execute_test(
            helpdesk_resource.create_ticket,
            title="Default origin ticket",
            content="This ticket should use default origin",
            agent_name=self.ticket_data["agent_name"],
            instance_id=self.ticket_data["instance_id"],
            api_version=self.ticket_data.get("api_version", "v1"),
        )

        assert isinstance(response, dict)
        assert "ticketname" in response

    @pytest.mark.dependency(depends=["create_ticket"], scope="session")
    @pytest.mark.order(122)
    def test_send_message(self, helpdesk_resource):
        """Test sending a message to an existing ticket."""
        assert hasattr(self, "ticket_id"), \
            "Ticket ID must be created before sending a message."

        response = execute_test(
            helpdesk_resource.send_message,
            ticket_id=self.ticket_id,
            content=self.ticket_data.get(
                "followup_message", "This is a test message."
            ),
            api_version=self.ticket_data.get("api_version", "v1"),
        )

        assert isinstance(response, dict)
        assert "ai_response" in response
        assert "chat_url" in response
        assert self.ticket_id in response["chat_url"]

    @pytest.mark.order(115)
    def test_list_workspaces(self, helpdesk_resource):
        """Test listing workspaces."""
        result = execute_test(helpdesk_resource.list_workspaces)
        assert isinstance(result, dict)
        assert "success" in result or isinstance(result, list)

    @pytest.mark.order(116)
    def test_list_projects(self, helpdesk_resource):
        """Test listing projects for the workspace."""
        result = execute_test(helpdesk_resource.list_projects)
        assert isinstance(result, (dict, list))
