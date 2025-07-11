from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("ai_helpdesk")
class AIHelpdesk(DuploTenantResourceV3):
    """Resource for creating tickets in the AI Service Helpdesk."""

    def __init__(self, duplo: DuploClient):
        super().__init__(duplo, "")  # No static endpoint; we build it dynamically

    @Command()
    def create_ticket(self,
                      title: args.TITLE,
                      agent_name: args.AGENTNAME,
                      instance_id: args.INSTANCEID,
                      api_version: args.APIVERSION) -> dict:
        """
        Create a ticket in the Duplo AI Service Helpdesk.

        Usage:
          duploctl ai_helpdesk create_ticket \
            --title "Pipeline failed" \
            --agent_name pytest-agent \
            --instance_id pytest-instance \
            [--api_version v1]

        Args:
          title: Title of the ticket (required).
          agent_name: The agent name (required).
          instance_id: The agent instance ID (required).
          api_version: Helpdesk API version (default: v1).

        Returns:
          Success message and ticket name.
        """
        
        if not title:
            raise DuploError("Ticket title cannot be empty.")

        if not agent_name:
            raise DuploError("Agent name cannot be empty.")

        if not instance_id:
            raise DuploError("Instance ID cannot be empty.")

        tenant_id = self.tenant["TenantId"]
        api_version = api_version.strip().lower()

        # Build dynamic path
        path = f"{api_version}/aiservicedesk/tickets/{tenant_id}"

        payload = {
            "title": title,
            "assignee": {
                "agentName": agent_name,
                "instanceId": instance_id,
                "agentHostTenantId": tenant_id
            }
        }

        try:
            response = self.duplo.post(path, payload)
            data = response.json()
            ticket_name = data.get("name")
             
            if not ticket_name or ticket_name == "null":
                raise DuploError(f"Could not extract ticket name from response.\nFull response: {response}")

            return {
                "message": f"Ticket created: {ticket_name}",
                "ticket_name": ticket_name
            }

        except Exception as ex:
            raise DuploError(f"Failed to create ticket: {str(ex)}")
