import pytest
from duplocloud.errors import DuploError
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

@pytest.mark.usefixtures("helpdesk_resource")
class TestDuploAI:
    """Integration tests for the AI Helpdesk ticketing system."""

    @pytest.mark.integration
    @pytest.mark.order(1)
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
        assert "response" in response
        assert isinstance(response["response"], str)

        # Save ticket ID for next test
        self.__class__.ticket_id = response["ticketname"]

    @pytest.mark.integration
    @pytest.mark.order(2)
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
        assert "response" in response
        assert "chat_url" in response
        assert self.ticket_id in response["chat_url"]