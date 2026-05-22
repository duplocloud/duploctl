import json
from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("ai", scope="tenant")
class DuploAI(DuploResourceV3):
  """Resource for creating tickets in the DuploCloud AI HelpDesk."""

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo, "")  # No static endpoint; we build it dynamically

  def _resolve_workspace_id(self, workspace_name: str, api_version: str) -> str:
    """Resolve an AI HelpDesk workspace name to its workspace ID.

    Args:
      workspace_name: The AI HelpDesk workspace name as shown in the portal.
      api_version: Helpdesk API version (e.g. ``v1``).

    Returns:
      The 24-character Mongo ObjectId for the matching workspace.

    Raises:
      DuploError: If zero or multiple workspaces match the given name.
    """
    workspaces_data = self.client.get(
        f"{api_version}/aiservicedesk/admin/data/workspaces"
        f"?filters[name]={quote_plus(workspace_name)}"
    ).json()
    items = workspaces_data.get("data", {}).get("items", [])
    target = workspace_name.lower()
    matches = [w for w in items if (w.get("name") or "").lower() == target]
    if not matches:
      raise DuploError(f"No AI HelpDesk workspace found with name '{workspace_name}'")
    if len(matches) > 1:
      raise DuploError(
          f"Multiple AI HelpDesk workspaces match name '{workspace_name}'; "
          "please use a unique name."
      )
    workspace_id = matches[0].get("id")
    if not workspace_id:
      raise DuploError(
          f"AI HelpDesk workspace '{workspace_name}' is missing an 'id' field "
          "in the API response."
      )
    return workspace_id

  def _resolve_agent_id(self, agent_name: str, api_version: str) -> str:
    """Resolve an AI agent name to its agent ID via the agents lookup.

    Raises ``DuploError`` if zero or multiple agents match, mirroring the
    workspace resolver's strict behavior so a duplicate-name backend state
    never silently picks the wrong agent.
    """
    agents_data = self.client.get(
        f"{api_version}/aiservicedesk/admin/data/aiagents"
        f"?filters[name]={quote_plus(agent_name)}"
    ).json()
    items = agents_data.get("data", {}).get("items", [])
    target = agent_name.lower()
    matches = [a for a in items if (a.get("name") or "").lower() == target]
    if not matches:
      raise DuploError(f"No AI agent found with name '{agent_name}'")
    if len(matches) > 1:
      raise DuploError(
          f"Multiple AI agents match name '{agent_name}'; "
          "please use a unique name or pass --agent_id."
      )
    agent_id = matches[0].get("id")
    if not agent_id:
      raise DuploError(
          f"AI agent '{agent_name}' is missing an 'id' field in the API response."
      )
    return agent_id

  def _agent_supports_streaming(self, agent_id: str, api_version: str) -> bool:
    """Return True if the agent's ``metaData.STREAMING_ENABLED`` is the string ``"true"``.

    The agent record's top-level ``doesSupportStreaming`` is unreliable on some
    portals — agents that actually stream still have it set to ``false``. The
    authoritative flag is the metadata entry.
    """
    resp = self.client.get(
        f"{api_version}/aiservicedesk/admin/data/aiagents/{agent_id}"
    ).json()
    agent = resp.get("data") if isinstance(resp.get("data"), dict) else resp
    metadata = agent.get("metaData") or {}
    return str(metadata.get("STREAMING_ENABLED", "")).strip().lower() == "true"

  @Command()
  def create_ticket(self,
                    title: args.TITLE,
                    workspace_name: args.WORKSPACENAME,
                    agent_id: args.AGENTID = None,
                    agent_name: args.AGENTNAME = None,
                    content: args.MESSAGE = None,
                    helpdesk_origin: args.HELPDESK_ORIGIN = None,
                    api_version: args.APIVERSION = "v1") -> dict:
    """Create DuploCloud AI ticket.

    Create a ticket in the DuploCloud AI HelpDesk. ``--workspace_name`` is
    required and is resolved to a workspace ID via the HelpDesk workspaces
    lookup. Provide either ``--agent_id`` (preferred, skips the agent lookup)
    or ``--agent_name`` (resolved against the AI HelpDesk agents API).

    When ``--content`` is provided, the initial message is sent to the agent.
    If the agent's ``metaData.STREAMING_ENABLED`` flag is ``"true"`` the
    ``sendMessageStreaming`` (SSE) endpoint is used; otherwise the plain
    ``sendMessage`` endpoint is used.

    Usage:
      ```sh
      duploctl ai create_ticket --title <title> --workspace_name <workspace> (--agent_id <id> | --agent_name <name>) [--content <content>] [--origin <origin>] [--api_version v1]
      ```

    Example: Create DuploCloud AI helpdesk ticket by agent ID
      ```sh
      duploctl ai create_ticket \\
        --title "Build pipeline failed for release-2025.07.10" \\
        --workspace_name "platform" \\
        --content "Build pipeline failed at unit test stage with error ..." \\
        --agent_id "agent-abc-123" \\
        --origin "pipelines" \\
        --api_version v1
      ```

    Example: Create DuploCloud AI helpdesk ticket by agent name
      ```sh
      duploctl ai create_ticket \\
        --title "Build pipeline failed" \\
        --workspace_name "platform" \\
        --agent_name "cicd"
      ```

    Args:
      title: Title of the ticket.
      workspace_name: The AI HelpDesk workspace name (visible in the portal). Resolved to a workspace ID.
      agent_id: The ID of the AI agent to assign the ticket to. Preferred over ``agent_name`` and skips the agents lookup.
      agent_name: The name of the AI agent to assign the ticket to. Ignored when ``agent_id`` is provided.
      content: Content or message of the ticket.
      helpdesk_origin: The helpdesk origin to use for the ticket (e.g., "pipelines", "api", "duploctl"). Defaults to "duploctl" if not specified.
      api_version: Helpdesk API version.

    Returns:
      ticket_response: A dictionary containing the following keys:
        ticketname : The name of the created AI helpdesk ticket.
        ai_response: The AI agent's response to the initial message, or None if no content was provided.
        chat_url: The URL to the helpdesk chat interface for the created ticket.

    Raises:
      DuploError: If the workspace name cannot be resolved, or if neither ``agent_id`` nor ``agent_name`` is provided, or if ``agent_name`` cannot be resolved.
    """
    api_version = api_version.strip().lower()

    workspace_id = self._resolve_workspace_id(workspace_name, api_version)

    if not agent_id:
      if not agent_name:
        raise DuploError("Either --agent_id or --agent_name is required")
      agent_id = self._resolve_agent_id(agent_name, api_version)

    payload = {
      "title": title,
      "aiAgentId": agent_id,
      "workspaceId": workspace_id,
      "source": "helpdesk",
      "Origin": helpdesk_origin if helpdesk_origin else "duploctl",
    }

    ticket_response = self.client.post(
        f"{api_version}/aiservicedesk/tickets/{workspace_id}", payload
    ).json()
    ticket_data = ticket_response.get("data") if isinstance(ticket_response.get("data"), dict) else ticket_response
    ticket_name = ticket_data.get("name") or ticket_data.get("Name")

    if not ticket_name or ticket_name == "null":
      raise DuploError(
          f"Could not extract ticket name from response.\nFull response: {ticket_response}"
      )

    ai_response = None
    if content:
      msg_result = self._send_message_to_workspace(
          workspace_id=workspace_id,
          ticket_id=ticket_name,
          content=content,
          api_version=api_version,
          agent_id=agent_id,
      )
      ai_response = msg_result.get("ai_response", {}).get("content")

    return {
      "ticketname": ticket_name,
      "chat_url": self._chat_url(workspace_id, ticket_name),
      "ai_response": ai_response,
    }

  @Command()
  def send_message(self,
                   workspace_name: args.WORKSPACENAME,
                   ticket_id: args.TICKETID,
                   content: args.MESSAGE,
                   api_version: args.APIVERSION = "v1") -> dict:
    """Send DuploCloud AI Message.

    Send a message to an existing ticket in the DuploCloud AI HelpDesk.
    ``--workspace_name`` is required and is resolved to a workspace ID via
    the HelpDesk workspaces lookup. The ticket is fetched to determine which
    agent handles it, and the appropriate sendMessage endpoint (streaming or
    non-streaming) is chosen based on the agent's
    ``metaData.STREAMING_ENABLED`` flag.

    Usage:
      ```sh
      duploctl ai send_message --workspace_name <workspace> --ticket_id <ticket id> --content <content>
      ```

    Example: Send a message to an AI helpdesk ticket
      ```sh
      duploctl ai send_message \\
        --workspace_name "platform" \\
        --ticket_id "andy-250717131532" \\
        --content "My app is still failing after restarting the pod." \\
        --api_version v1
      ```

    Args:
      workspace_name: The AI HelpDesk workspace name (visible in the portal).
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
    workspace_id = self._resolve_workspace_id(workspace_name, api_version)
    agent_id = self._agent_id_from_ticket(workspace_id, ticket_id, api_version)
    return self._send_message_to_workspace(
        workspace_id=workspace_id,
        ticket_id=ticket_id,
        content=content,
        api_version=api_version,
        agent_id=agent_id,
    )

  def _agent_id_from_ticket(self,
                            workspace_id: str,
                            ticket_id: str,
                            api_version: str) -> str:
    """Fetch the ticket and return its assigned ``aiAgentId``."""
    resp = self.client.get(
        f"{api_version}/aiservicedesk/tickets/{workspace_id}/{ticket_id}"
    ).json()
    ticket = resp.get("data") if isinstance(resp.get("data"), dict) else resp
    agent_id = ticket.get("aiAgentId") or ticket.get("AIAgentId")
    if not agent_id:
      raise DuploError(
          f"Could not determine assigned agent for ticket '{ticket_id}' "
          "in the AI HelpDesk response."
      )
    return agent_id

  def _send_message_to_workspace(self,
                                 workspace_id: str,
                                 ticket_id: str,
                                 content: str,
                                 api_version: str,
                                 agent_id: str) -> dict:
    """Dispatch to the streaming or non-streaming sendMessage endpoint."""
    if self._agent_supports_streaming(agent_id, api_version):
      ai_response = self._send_message_streaming(
          workspace_id, ticket_id, content, api_version)
    else:
      ai_response = self._send_message_non_streaming(
          workspace_id, ticket_id, content, api_version)
    return {
      "ai_response": ai_response,
      "chat_url": self._chat_url(workspace_id, ticket_id),
    }

  def _send_message_non_streaming(self,
                                  workspace_id: str,
                                  ticket_id: str,
                                  content: str,
                                  api_version: str) -> dict:
    """POST to the unary sendMessage endpoint and return the JSON reply."""
    path = f"{api_version}/aiservicedesk/tickets/{workspace_id}/{ticket_id}/sendMessage"
    payload = {
      "content": content,
      "data": {},
      "platform_context": {},
    }
    return self.client.post(path, payload).json()

  def _send_message_streaming(self,
                              workspace_id: str,
                              ticket_id: str,
                              content: str,
                              api_version: str) -> dict:
    """POST to the SSE sendMessageStreaming endpoint and assemble the reply.

    Routes through ``DuploAPI.stream_post`` so URL construction, auth header
    injection, timeout, exception translation, and status validation are
    identical to non-streaming calls — the streaming transport is the only
    difference.

    The endpoint returns ``text/event-stream`` chunks; each event is
    ``event: <type>\\ndata: <json>\\n\\n``. The agent emits ``text_delta``
    chunks for the visible reply, ``error`` events on failure, and a final
    ``done`` chunk. This consumer concatenates the ``text_delta`` texts and
    returns a dict shaped like the unary reply so callers don't need to
    branch on transport.
    """
    path = (
        f"{api_version}/aiservicedesk/tickets/"
        f"{workspace_id}/{ticket_id}/sendMessageStreaming"
    )
    payload = {
      "content": content,
      "data": {},
      "platform_context": {},
    }

    text_parts: list[str] = []
    raw_events: list[dict] = []
    with self.client.stream_post(
        path, payload, extra_headers={"Accept": "text/event-stream"},
    ) as resp:
      for raw_line in resp.iter_lines(decode_unicode=True):
        if not raw_line or not raw_line.startswith("data:"):
          continue
        data_str = raw_line[len("data:"):].strip()
        if not data_str:
          continue
        try:
          event = json.loads(data_str)
        except json.JSONDecodeError:
          continue
        raw_events.append(event)
        etype = event.get("type")
        if etype == "text_delta":
          text_parts.append(event.get("text", ""))
        elif etype == "error":
          raise DuploError(
              f"Agent stream error: {event.get('error') or event}")
        elif etype == "done":
          break

    return {
      "content": "".join(text_parts),
      "role": "assistant",
      "events": raw_events,
    }

  def _chat_url(self, workspace_id: str, ticket_id: str) -> str:
    """Build the helpdesk chat URL for a ticket in the given workspace."""
    return f"{self.duplo.host}/app/ai/service-desk/{workspace_id}/tickets/chat/{ticket_id}"
