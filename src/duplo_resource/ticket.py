import json
from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("ticket", scope="tenant")
class DuploTicket(DuploResource):
  """Manage AI HelpDesk tickets in DuploCloud.

  Tickets live inside an AI HelpDesk workspace and are handled by an
  agent. Workspace and agent resolution is delegated to the
  ``workspace`` and ``agent`` resources so the same name-or-id lookup
  is shared across the CLI.
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo, api_version="v1")
    self.__workspace_svc = self.duplo.load("workspace")
    self.__agent_svc = self.duplo.load("agent")

  def _data(self, response: dict) -> dict:
    """Unwrap a single-object envelope ``{success, data: {...}}``."""
    data = response.get("data")
    return data if isinstance(data, dict) else response

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None,
           workspace: args.WORKSPACE = None,
           workspace_id: args.WORKSPACEID = None,
           api_version: args.APIVERSION = "v1") -> dict:
    """Find an AI HelpDesk ticket within a workspace.

    The ticket is fetched directly by its identifier (name or ``--id``).
    The workspace is resolved via ``--workspace`` (name) or
    ``--workspace-id``.

    Usage: CLI Usage
      ```sh
      duploctl ticket find <name> --workspace <workspace>
      duploctl ticket find --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.
      workspace: The workspace name the ticket belongs to.
      workspace_id: The workspace id the ticket belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The ticket object.

    Raises:
      DuploError: If no ticket identifier or workspace selector is given.
    """
    api_version = api_version.strip().lower()
    identifier = id or name
    if not identifier:
      raise DuploError("Either a ticket name or --id is required")
    wid = self.__workspace_svc.find(
        name=workspace, id=workspace_id, api_version=api_version)["id"]
    response = self.client.get(
        f"{api_version}/aiservicedesk/tickets/"
        f"{wid}/{quote_plus(identifier)}").json()
    return self._data(response)

  @Command()
  def create_ticket(self,
                    title: args.TITLE,
                    workspace: args.WORKSPACE = None,
                    workspace_id: args.WORKSPACEID = None,
                    agent_id: args.AGENTID = None,
                    agent_name: args.AGENTNAME = None,
                    content: args.MESSAGE = None,
                    helpdesk_origin: args.HELPDESK_ORIGIN = None,
                    streaming: args.STREAMING = False,
                    api_version: args.APIVERSION = "v1") -> dict:
    """Create an AI HelpDesk ticket.

    The workspace is resolved via ``--workspace`` (name) or
    ``--workspace-id``. Provide either ``--agent_id`` (preferred, skips
    the lookup) or ``--agent_name`` (resolved via the ``agent``
    resource). When ``--content`` is supplied the initial message is
    sent to the agent.

    Usage: CLI Usage
      ```sh
      duploctl ticket create_ticket --title <title> --workspace <workspace> (--agent_id <id> | --agent_name <name>) [--content <content>]
      ```

    Args:
      title: Title of the ticket.
      workspace: The workspace name the ticket belongs to.
      workspace_id: The workspace id the ticket belongs to.
      agent_id: The agent id to assign. Preferred over agent_name.
      agent_name: The agent name to assign. Ignored when agent_id is set.
      content: Optional initial message to send to the agent.
      helpdesk_origin: The helpdesk origin (defaults to "duploctl").
      streaming: Force the streaming send endpoint for the message.
      api_version: Helpdesk API version.

    Returns:
      ticket_response: A dict with ``ticketname``, ``ai_response`` and
        ``chat_url`` keys.

    Raises:
      DuploError: If the workspace cannot be resolved, or if neither
        agent_id nor agent_name is provided.
    """
    api_version = api_version.strip().lower()
    workspace_id = self.__workspace_svc.find(
        name=workspace, id=workspace_id, api_version=api_version)["id"]

    if not agent_id:
      if not agent_name:
        raise DuploError("Either --agent_id or --agent_name is required")
      agent_id = self.__agent_svc.find(
          name=agent_name, api_version=api_version)["id"]

    payload = {
      "title": title,
      "aiAgentId": agent_id,
      "workspaceId": workspace_id,
      "source": "helpdesk",
      "Origin": helpdesk_origin or "duploctl",
    }
    response = self.client.post(
        f"{api_version}/aiservicedesk/tickets/{workspace_id}",
        payload).json()
    ticket = self._data(response)
    ticket_name = ticket.get("name") or ticket.get("Name")
    if not ticket_name or ticket_name == "null":
      raise DuploError(
          f"Could not extract ticket name from response.\n"
          f"Full response: {response}")

    ai_response = None
    if content:
      msg = self._dispatch_message(
          workspace_id=workspace_id,
          ticket_id=ticket_name,
          content=content,
          agent_id=agent_id,
          streaming=streaming,
          api_version=api_version,
      )
      ai_response = msg.get("ai_response", {}).get("content")

    return {
      "ticketname": ticket_name,
      "chat_url": self._chat_url(workspace_id, ticket_name),
      "ai_response": ai_response,
    }

  @Command()
  def send_message(self,
                   name: args.NAME = None,
                   id: args.ID = None,
                   workspace: args.WORKSPACE = None,
                   workspace_id: args.WORKSPACEID = None,
                   content: args.MESSAGE = None,
                   streaming: args.STREAMING = False,
                   api_version: args.APIVERSION = "v1") -> dict:
    """Send a message to an existing AI HelpDesk ticket.

    The ticket's assigned agent is fetched to decide whether to use the
    streaming endpoint; ``--streaming`` forces it on regardless.

    Usage: CLI Usage
      ```sh
      echo "the message" | duploctl ticket send_message --id <id> --workspace <workspace> -f -
      duploctl ticket send_message --id <id> --workspace <workspace> --content "the message"
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.
      workspace: The workspace name the ticket belongs to.
      workspace_id: The workspace id the ticket belongs to.
      content: The message text. Pass it inline with ``--content`` or
        read from stdin with ``-f -``.
      streaming: Force the streaming send endpoint.
      api_version: Helpdesk API version.

    Returns:
      chat_response: A dict with ``ai_response`` and ``chat_url`` keys.

    Raises:
      DuploError: If no ticket identifier, workspace, or message is
        provided.
    """
    api_version = api_version.strip().lower()
    identifier = id or name
    if not identifier:
      raise DuploError("Either a ticket name or --id is required")
    if not content or not content.strip():
      raise DuploError(
          "Message content is required (pass --content or pipe with -f -).")
    workspace_id = self.__workspace_svc.find(
        name=workspace, id=workspace_id, api_version=api_version)["id"]
    agent_id = self._agent_id_from_ticket(
        workspace_id, identifier, api_version)
    return self._dispatch_message(
        workspace_id=workspace_id,
        ticket_id=identifier,
        content=content,
        agent_id=agent_id,
        streaming=streaming,
        api_version=api_version,
    )

  def _agent_id_from_ticket(self,
                            workspace_id: str,
                            ticket_id: str,
                            api_version: str) -> str:
    """Fetch the ticket and return its assigned ``aiAgentId``."""
    response = self.client.get(
        f"{api_version}/aiservicedesk/tickets/"
        f"{workspace_id}/{ticket_id}").json()
    ticket = self._data(response)
    agent_id = ticket.get("aiAgentId") or ticket.get("AIAgentId")
    if not agent_id:
      raise DuploError(
          f"Could not determine assigned agent for ticket '{ticket_id}' "
          "in the AI HelpDesk response.")
    return agent_id

  def _dispatch_message(self,
                        workspace_id: str,
                        ticket_id: str,
                        content: str,
                        agent_id: str,
                        streaming: bool,
                        api_version: str) -> dict:
    """Send a message, choosing the streaming or unary endpoint.

    Streaming is used when ``--streaming`` is set or when the assigned
    agent advertises ``metaData.STREAMING_ENABLED``. The helpdesk's
    non-streaming deserializer chokes on the NDJSON a streaming agent
    emits, so honoring the agent's own flag keeps the call correct even
    without ``--streaming``.
    """
    use_streaming = streaming or self.__agent_svc.supports_streaming(
        id=agent_id, api_version=api_version)
    send = self._send_streaming if use_streaming else self._send_unary
    ai_response = send(workspace_id, ticket_id, content, api_version)
    return {
      "ai_response": ai_response,
      "chat_url": self._chat_url(workspace_id, ticket_id),
    }

  def _send_unary(self,
                  workspace_id: str,
                  ticket_id: str,
                  content: str,
                  api_version: str) -> dict:
    """POST to the unary sendMessage endpoint and return the JSON reply."""
    path = (f"{api_version}/aiservicedesk/tickets/"
            f"{workspace_id}/{ticket_id}/sendMessage")
    return self.client.post(path, self._message_payload(content)).json()

  def _send_streaming(self,
                      workspace_id: str,
                      ticket_id: str,
                      content: str,
                      api_version: str) -> dict:
    """POST to the SSE sendMessageStreaming endpoint and assemble the reply.

    Routes through ``DuploAPI.post(..., stream=True)`` so URL
    construction, auth header injection, timeout, exception translation,
    and status validation are identical to the unary call — the
    streaming transport is the only difference. Each event is
    ``data: <json>``; ``text_delta`` chunks are concatenated, ``error``
    events raise, and ``done`` ends the stream.
    """
    path = (f"{api_version}/aiservicedesk/tickets/"
            f"{workspace_id}/{ticket_id}/sendMessageStreaming")
    text_parts: list[str] = []
    raw_events: list[dict] = []
    with self.client.post(
        path, self._message_payload(content),
        headers={"Accept": "text/event-stream"}, stream=True,
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

  def _message_payload(self, content: str) -> dict:
    """Build the sendMessage request body for the given content."""
    return {"content": content, "data": {}, "platform_context": {}}

  def _chat_url(self, workspace_id: str, ticket_id: str) -> str:
    """Build the helpdesk chat URL for a ticket in the workspace."""
    return (f"{self.duplo.host}/app/ai/service-desk/"
            f"{workspace_id}/tickets/chat/{ticket_id}")

  @Command("ls")
  def list(self,
           workspace: args.WORKSPACE = None,
           workspace_id: args.WORKSPACEID = None,
           api_version: args.APIVERSION = "v1") -> list:
    """List the tickets in an AI HelpDesk workspace.

    Usage: CLI Usage
      ```sh
      duploctl ticket list --workspace <workspace>
      duploctl ticket list --workspace-id <workspace id>
      ```

    Args:
      workspace: The workspace name the tickets belong to.
      workspace_id: The workspace id the tickets belong to.
      api_version: Helpdesk API version.

    Returns:
      list: The tickets in the workspace.
    """
    api_version = api_version.strip().lower()
    wid = self.__workspace_svc.find(
        name=workspace, id=workspace_id, api_version=api_version)["id"]
    response = self.client.get(
        f"{api_version}/aiservicedesk/tickets/{wid}").json()
    if isinstance(response, dict):
      data = response.get("data", response)
      return data.get("items", data) if isinstance(data, dict) else data
    return response

  @Command()
  def assignee(self,
               name: args.NAME = None,
               id: args.ID = None,
               workspace: args.WORKSPACE = None,
               workspace_id: args.WORKSPACEID = None,
               api_version: args.APIVERSION = "v1") -> dict:
    """Get the agent currently assigned to a ticket.

    Usage: CLI Usage
      ```sh
      duploctl ticket assignee <name> --workspace <workspace>
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.
      workspace: The workspace name the ticket belongs to.
      workspace_id: The workspace id the ticket belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The assigned agent object.

    Raises:
      DuploError: If no ticket identifier is given.
    """
    api_version = api_version.strip().lower()
    identifier = id or name
    if not identifier:
      raise DuploError("Either a ticket name or --id is required")
    wid = self.__workspace_svc.find(
        name=workspace, id=workspace_id, api_version=api_version)["id"]
    response = self.client.get(
        f"{api_version}/aiservicedesk/tickets/"
        f"{wid}/{quote_plus(identifier)}/assignee").json()
    return self._data(response)

  @Command()
  def reassign(self,
               name: args.NAME = None,
               id: args.ID = None,
               agent_name: args.AGENTNAME = None,
               agent_id: args.AGENTID = None,
               workspace: args.WORKSPACE = None,
               workspace_id: args.WORKSPACEID = None,
               api_version: args.APIVERSION = "v1") -> dict:
    """Reassign a ticket to a different agent.

    The agent is resolved by name or id via the ``agent`` resource.

    Usage: CLI Usage
      ```sh
      duploctl ticket reassign <name> --workspace <workspace> --agent <agent>
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.
      agent_name: The agent name to assign.
      agent_id: The agent id to assign. Skips the agent name lookup.
      workspace: The workspace name the ticket belongs to.
      workspace_id: The workspace id the ticket belongs to.
      api_version: Helpdesk API version.

    Returns:
      message: A success message.

    Raises:
      DuploError: If no ticket identifier is given.
      DuploNotFound: If the agent cannot be found.
    """
    api_version = api_version.strip().lower()
    identifier = id or name
    if not identifier:
      raise DuploError("Either a ticket name or --id is required")
    wid = self.__workspace_svc.find(
        name=workspace, id=workspace_id, api_version=api_version)["id"]
    aid = self.__agent_svc.find(
        name=agent_name, id=agent_id, api_version=api_version)["id"]
    self.client.put(
        f"{api_version}/aiservicedesk/tickets/"
        f"{wid}/{quote_plus(identifier)}/assignee/{quote_plus(aid)}")
    return {"message": f"ticket '{identifier}' reassigned to agent "
                       f"'{agent_name or agent_id}'"}

  @Command()
  def set_status(self,
                 name: args.NAME = None,
                 id: args.ID = None,
                 status: args.TICKET_STATUS = None,
                 disposition: args.TICKET_DISPOSITION = None,
                 workspace: args.WORKSPACE = None,
                 workspace_id: args.WORKSPACEID = None,
                 api_version: args.APIVERSION = "v1") -> dict:
    """Set a ticket's status.

    When ``--status closed`` is used, ``--disposition`` (``resolved`` or
    ``unResolved``) is required by the backend.

    Usage: CLI Usage
      ```sh
      duploctl ticket set_status <name> --workspace <workspace> --status inProgress
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.
      status: The new status (open, inProgress, waitingForUserInput,
        waitingForUserAgent, closed).
      disposition: The disposition (resolved, unResolved); required when
        closing.
      workspace: The workspace name the ticket belongs to.
      workspace_id: The workspace id the ticket belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The updated ticket object.

    Raises:
      DuploError: If no ticket identifier or status is given.
    """
    api_version = api_version.strip().lower()
    identifier = id or name
    if not identifier:
      raise DuploError("Either a ticket name or --id is required")
    if not status:
      raise DuploError("--status is required")
    wid = self.__workspace_svc.find(
        name=workspace, id=workspace_id, api_version=api_version)["id"]
    body = {"status": status}
    if disposition:
      body["disposition"] = disposition
    response = self.client.put(
        f"{api_version}/aiservicedesk/tickets/"
        f"{wid}/{quote_plus(identifier)}/status", body).json()
    return self._data(response)

  @Command()
  def close(self,
            name: args.NAME = None,
            id: args.ID = None,
            disposition: args.TICKET_DISPOSITION = "resolved",
            workspace: args.WORKSPACE = None,
            workspace_id: args.WORKSPACEID = None,
            api_version: args.APIVERSION = "v1") -> dict:
    """Close a ticket.

    Convenience wrapper for ``set_status --status closed``. The backend
    requires a disposition when closing; defaults to ``resolved``.

    Usage: CLI Usage
      ```sh
      duploctl ticket close <name> --workspace <workspace>
      duploctl ticket close <name> --workspace <workspace> --disposition unResolved
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.
      disposition: The disposition (resolved, unResolved). Defaults to
        resolved.
      workspace: The workspace name the ticket belongs to.
      workspace_id: The workspace id the ticket belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The updated ticket object.
    """
    return self.set_status(
        name=name, id=id, status="closed", disposition=disposition,
        workspace=workspace, workspace_id=workspace_id,
        api_version=api_version)

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None,
             workspace: args.WORKSPACE = None,
             workspace_id: args.WORKSPACEID = None,
             api_version: args.APIVERSION = "v1") -> dict:
    """Delete an AI HelpDesk ticket from a workspace.

    Usage: CLI Usage
      ```sh
      duploctl ticket delete <name> --workspace <workspace>
      duploctl ticket delete --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.
      workspace: The workspace name the ticket belongs to.
      workspace_id: The workspace id the ticket belongs to.
      api_version: Helpdesk API version.

    Returns:
      message: A success message.

    Raises:
      DuploError: If no ticket identifier is given.
    """
    api_version = api_version.strip().lower()
    identifier = id or name
    if not identifier:
      raise DuploError("Either a ticket name or --id is required")
    wid = self.__workspace_svc.find(
        name=workspace, id=workspace_id, api_version=api_version)["id"]
    self.client.delete(
        f"{api_version}/aiservicedesk/tickets/"
        f"{wid}/{quote_plus(identifier)}")
    return {"message": f"ticket '{identifier}' deleted"}
