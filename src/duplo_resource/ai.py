from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("ai")
class AIHelpdesk(DuploTenantResourceV3):
    """Resource for creating tickets in the DuploCloud AI HelpDesk."""

    def __init__(self, duplo: DuploClient):
        super().__init__(duplo, "")  # No static endpoint; we build it dynamically    

    @Command()
    def create_ticket(self,
                    title: args.TITLE,
                    content: args.MESSAGE,   
                    agent_name: args.AGENTNAME,
                    instance_id: args.INSTANCEID,
                    api_version: args.APIVERSION) -> dict:
        """
        Create a ticket in the DuploCloud AI HelpDesk.

        Usage:
            ```sh
            duploctl ai create_ticket \
                --title "Pipeline failed" \
                --content "Pipeline failed" \
                --agent_name pytest-agent \
                --instance_id pytest-instance \
                [--api_version v1]
            ```

        Example:
            Create a ticket for a failed build pipeline in test environment:
            ```sh
            duploctl ai create_ticket \
                --title "Build pipeline failed for release-2025.07.10" \
                --content "Build pipeline failed at unit test stage with error ..." \
                --agent_name "cicd" \
                --instance_id "cicd" \
                --api_version v1
            ```            

        Args:
            title: Title of the ticket (required).
            content: Content or message of the ticket(required).
            agent_name: The agent name (required).
            instance_id: The agent instance ID (required).
            api_version: Helpdesk API version (default: v1).

        Returns:
            Ticket name, AI Agent reponse &  a Chat url.
        """
        
        if not title:
            raise DuploError("Ticket title cannot be empty.")
        
        if not content:
            raise DuploError("Ticket content cannot be empty.")

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
            "content": content,
            "assignee": {
                "agentName": agent_name,   
                "instanceId": instance_id,
                "agentHostTenantId": tenant_id
            }
        }

        response = self.duplo.post(path, payload)
        data = response.json()
        ticket = data.get("ticket", {})
        ticket_name = ticket.get("name")
        ai_response = data.get("message")
            
        if not ticket_name or ticket_name == "null":
            raise DuploError(f"Could not extract ticket name from response.\nFull response: {response.text}")

        if not ai_response or ai_response == "null":
            raise DuploError(f"Could not extract AI Response.\nFull response: {response.text}")

        return {
            "ticketname": ticket_name,
            "chat_url": f"{self.duplo.host}/app/ai/service-desk/{tenant_id}/tickets/chat/{ticket_name}",
            "response": ai_response
        }
    

    @Command()
    def send_message(self,
                    ticket_id: args.TICKETID,
                    content: args.MESSAGE,
                    api_version: args.APIVERSION = "v1") -> dict:
        """
        Send a message to an existing ticket in the DuploCloud AI HelpDesk.

        Usage:
            duploctl ai send_message \
                --ticket_id "andy-250717131532" \
                --content "My app pod is crashing."

        Args:
            ticket_id: Ticket ID to send the message to (required).
            content: The message content (required).
            api_version: Helpdesk API version (default: v1).

        Returns:
            JSON response from agent and a direct chat URL.
        """
        if not ticket_id:
            raise DuploError("Ticket ID is required.")

        if not content:
            raise DuploError("Message content cannot be empty.")

        api_version = api_version.strip().lower()
        tenant_id = self.tenant["TenantId"]

        path = f"{api_version}/aiservicedesk/tickets/{tenant_id}/{ticket_id}/sendmessage"

        payload = {
            "content": content,
            "data": {},
            "platform_context": {}
        }

        response = self.duplo.post(path, payload)
        result = response.json()

        return {
            "response": result,
            "chat_url": f"{self.duplo.host}/app/ai/service-desk/{tenant_id}/tickets/chat/{ticket_id}"
        }
