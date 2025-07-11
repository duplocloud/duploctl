import pytest
from duplocloud.errors import DuploError
from .conftest import get_test_data

@pytest.fixture(scope="class")
def helpdesk_resource(duplo, request):
    """Fixture to load the AI Helpdesk resource and test data."""
    resource = duplo.load("ai_helpdesk")  
    request.cls.ticket_data = get_test_data("ticket")
    return resource

def execute_test(func, *args, **kwargs):
    """Helper to execute a test and capture DuploError cleanly."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")

@pytest.mark.usefixtures("helpdesk_resource")
class TestAIHelpdesk:
    """Integration tests for the AI Helpdesk ticketing system."""

    @pytest.mark.integration
    @pytest.mark.order(1)
    def test_create_ticket(self, helpdesk_resource):
        """Test creating a helpdesk ticket."""
        response = execute_test(
            helpdesk_resource.create_ticket,
            title=self.ticket_data["title"],
            agent_name=self.ticket_data["agent_name"],
            instance_id=self.ticket_data["instance_id"],
            api_version=self.ticket_data.get("api_version", "v1")
        )

        assert isinstance(response, dict)
        assert "ticket_name" in response
        assert response["ticket_name"]
        assert response["message"].startswith("Ticket created:")
