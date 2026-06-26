import pytest
from duplocloud.commander import commands_for
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResourceV2, DuploResourceV3
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


@pytest.mark.unit
def test_ai_is_non_crud_resource():
    """The `ai` resource must not inherit a CRUD base class.

    The helpdesk API has no list/find/create/update/delete/apply routes that
    fit the V2/V3 contract; extending one of those bases would re-expose the
    inherited commands with broken URLs (empty-slug `v3/subscriptions/{tid}//`)
    and mislead users via `duploctl ai --help` and the auto-generated docs.
    """
    assert DuploResourceV3 not in DuploAI.__mro__, (
        "DuploAI must not inherit from DuploResourceV3 (non-CRUD resource)"
    )
    assert DuploResourceV2 not in DuploAI.__mro__, (
        "DuploAI must not inherit from DuploResourceV2 (non-CRUD resource)"
    )


@pytest.mark.unit
def test_ai_exposes_only_real_commands():
    """Only `create_ticket` and `send_message` should appear as @Command-decorated methods.

    Locks against accidentally re-adding a CRUD base class (which would
    re-register inherited list/find/create/update/delete/apply commands) or
    adding new commands without updating this assertion.
    """
    assert set(commands_for("ai").keys()) == {"create_ticket", "send_message"}


@pytest.mark.unit
def test_ai_instance_is_callable():
    """DuploAI instances must be callable for CLI dispatch.

    DuploCtl.__call__ invokes a loaded resource as ``r(*args, **kwargs)`` to
    route subcommands; without ``__call__`` on the class, ``duploctl ai
    create_ticket`` and ``duploctl ai send_message`` raise TypeError before
    any command method runs. The @Resource decorator does NOT inject
    __call__ — it must come from extending ``DuploResource`` (v1 base).
    """
    class _FakeClient:
        pass

    class _FakeDuplo:
        def load(self, _name):
            return None

        def load_client(self, _name):
            return _FakeClient()

    ai = DuploAI(_FakeDuplo())
    assert callable(ai), (
        "DuploAI instance must be callable — required for CLI subcommand dispatch"
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
            content=self.ticket_data["message"],
            agent_name=self.ticket_data["agent_name"],
            instance_id=self.ticket_data["instance_id"],
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
            content="This ticket was created from a pipeline",
            agent_name=self.ticket_data["agent_name"],
            instance_id=self.ticket_data["instance_id"],
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
            content="This ticket should use default origin",
            agent_name=self.ticket_data["agent_name"],
            instance_id=self.ticket_data["instance_id"],
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
            ticket_id=self.ticket_id,
            content=self.ticket_data.get("followup_message", "This is a test message."),
            api_version=self.ticket_data.get("api_version", "v1")
        )

        assert isinstance(response, dict)
        assert "ai_response" in response
        assert "chat_url" in response
        assert self.ticket_id in response["chat_url"]
