from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("ai")
class DuploAI(DuploTenantResourceV3):
  """Resource for creating tickets in the DuploCloud AI HelpDesk."""

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "")  # No static endpoint; we build it dynamically

  @Command()
  def create_ticket(self,
                    title: args.TITLE,
                    agent_name: args.AGENTNAME,
                    instance_id: args.INSTANCEID,
                    content: args.MESSAGE = None,
                    helpdesk_origin: args.HELPDESK_ORIGIN = None,
                    api_version: args.APIVERSION = "v1") -> dict:
    """Create DuploCloud AI ticket.

    Create a ticket in the DuploCloud AI HelpDesk.

    Usage:
      ```sh
      duploctl ai create_ticket --title <title> --content <content> --agent_name <agent name> --instance_id <instance id> [--origin <origin>] [--api_version v1]
      ```

    Example: Create DuploCloud AI helpdesk ticket
      Run this command Create a ticket for a failed build pipeline in test environment.

      ```sh
      duploctl ai create_ticket \\
        --title "Build pipeline failed for release-2025.07.10" \\
        --content "Build pipeline failed at unit test stage with error ..." \\
        --agent_name "cicd" \\
        --instance_id "cicd" \\
        --origin "pipelines" \\
        --api_version v1
      ```

    Args:
      title: Title of the ticket.
      agent_name: The agent name.
      instance_id: The agent instance ID.
      content: Content or message of the ticket.
      helpdesk_origin: The helpdesk origin to use for the ticket (e.g., "pipelines", "api", "duploctl"). Defaults to "duploctl" if not specified.
      api_version: Helpdesk API version.

    Returns:
      ticket_response: A dictionary containing the following keys:
        ticketname : The name of the created AI helpdesk ticket.
        ai_response: The AI agent's response object or message content returned from the service.
        chat_url: The URL to the helpdesk chat interface for the created ticket.
    """
    tenant_id = self.tenant_id
    api_version = api_version.strip().lower()

    # Build dynamic path
    path = f"{api_version}/aiservicedesk/tickets/{tenant_id}"

    payload = {
      "title": title,
      "assignee": {
        "agentName": agent_name,
        "instanceId": instance_id
      }
    }

    if content:
      payload["content"] = content
      payload["process_message"] = True

    # Always include Origin field, defaulting to "duploctl" if not specified
    payload["Origin"] = helpdesk_origin if helpdesk_origin else "duploctl"

    response = self.duplo.post(path, payload)
    data = response.json()
    ticket = data.get("ticket", {})
    ticket_name = ticket.get("name")
    ai_response = data.get("message")

    if not ticket_name or ticket_name == "null":
      raise DuploError(f"Could not extract ticket name from response.\nFull response: {response.text}")

    return {
      "ticketname": ticket_name,
      "chat_url": f"{self.duplo.host}/app/ai/service-desk/{tenant_id}/tickets/chat/{ticket_name}",
      "ai_response": ai_response
    }

  @Command()
  def send_message(self,
                   ticket_id: args.TICKETID,
                   content: args.MESSAGE,
                   api_version: args.APIVERSION = "v1") -> dict:
    """Send DuploCloud AI Message.

    Send a message to an existing ticket in the DuploCloud AI HelpDesk.

    Usage:
      ```sh
      duploctl ai send_message --ticket_id <ticket id> --content <content>
      ```

    Example: Send a message to an AI helpdesk ticket
      Run this command to send a message to ai helpdesk ticket.

      ```sh
      duploctl ai send_message \\
        --ticket_id "andy-250717131532" \\
        --content "My app is still failing after restarting the pod." \\
        --api_version v1
      ```

    Args:
      ticket_id: Ticket ID to send the message to.
      content: The message content.
      api_version: Helpdesk API version.

    Returns:
      chat_response: A dictionary containing the following keys:
        ai_response: The AI agent's response object or message content returned from the service.
        chat_url: The URL to the helpdesk chat interface for the specified ticket.
    """
    if not content or not content.strip():
      raise ValueError("The 'content' parameter is required and cannot be empty.")

    api_version = api_version.strip().lower()
    tenant_id = self.tenant_id

    path = f"{api_version}/aiservicedesk/tickets/{tenant_id}/{ticket_id}/sendmessage"

    payload = {
      "content": content,
      "data": {},
      "platform_context": {}
    }

    response = self.duplo.post(path, payload)
    result = response.json()

    return {
      "ai_response": result,
      "chat_url": f"{self.duplo.host}/app/ai/service-desk/{tenant_id}/tickets/chat/{ticket_id}"
    }
