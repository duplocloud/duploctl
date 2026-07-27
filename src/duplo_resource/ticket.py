import json
from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
from duplo_resource.helpdesk_client import unwrap_data
import duplocloud.args as args


@Resource("ticket", scope="workspace", client="helpdesk")
class DuploTicket(DuploResource):
  """Manage AI HelpDesk tickets in DuploCloud.

  Tickets live inside an AI HelpDesk workspace and are handled by an
  agent. The workspace comes from the workspace scope — the global
  ``-W/--workspace`` or ``--workspace-id`` flags (or ``DUPLO_WORKSPACE``
  / ``DUPLO_WORKSPACE_ID``) — resolved lazily through the ``workspace``
  resource. Agent resolution is delegated to the ``agent`` resource so
  the same name-or-id lookup is shared across the CLI.
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)
    self.__agent_svc = self.duplo.load("agent")

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None) -> dict:
    """Find an AI HelpDesk ticket within the workspace.

    The ticket is fetched directly by its identifier (name or ``--id``)
    from the workspace selected by the global ``-W/--workspace`` or
    ``--workspace-id`` flags.

    Usage: CLI Usage
      ```sh
      duploctl ticket find <name> -W <workspace>
      duploctl ticket find --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.

    Returns:
      resource: The ticket object.

    Raises:
      DuploError: If no ticket identifier or workspace selector is given.
    """
    identifier = id or name
    if not identifier:
      raise DuploError("Either a ticket name or --id is required")
    response = self.client.get(
        f"tickets/{self.workspace_id}/{quote_plus(identifier)}").json()
    return unwrap_data(response)

  @Command()
  def create_ticket(self,
                    title: args.TITLE,
                    agent_id: args.AGENTID = None,
                    agent_name: args.AGENTNAME = None,
                    content: args.MESSAGE = None,
                    helpdesk_origin: args.HELPDESK_ORIGIN = None,
                    streaming: args.STREAMING = False) -> dict:
    """Create an AI HelpDesk ticket.

    The ticket is created in the workspace selected by the global
    ``-W/--workspace`` or ``--workspace-id`` flags. Provide either
    ``--agent_id`` (preferred, skips the lookup) or ``--agent_name``
    (resolved via the ``agent`` resource). When ``--content`` is
    supplied the initial message is sent to the agent.

    Usage: CLI Usage
      ```sh
      duploctl ticket create_ticket --title <title> -W <workspace> (--agent_id <id> | --agent_name <name>) [--content <content>]
      ```

    Args:
      title: Title of the ticket.
      agent_id: The agent id to assign. Preferred over agent_name.
      agent_name: The agent name to assign. Ignored when agent_id is set.
      content: Optional initial message to send to the agent.
      helpdesk_origin: The helpdesk origin (defaults to "duploctl").
      streaming: Force the streaming send endpoint for the message.

    Returns:
      ticket_response: A dict with ``ticketname``, ``ai_response`` and
        ``chat_url`` keys.

    Raises:
      DuploError: If the workspace cannot be resolved, or if neither
        agent_id nor agent_name is provided.
    """
    workspace_id = self.workspace_id

    if not agent_id:
      if not agent_name:
        raise DuploError("Either --agent_id or --agent_name is required")
      agent_id = self.__agent_svc.find(name=agent_name)["id"]

    payload = {
      "title": title,
      "aiAgentId": agent_id,
      "workspaceId": workspace_id,
      "source": "helpdesk",
      "Origin": helpdesk_origin or "duploctl",
    }
    response = self.client.post(
        f"tickets/{workspace_id}", payload).json()
    ticket = unwrap_data(response)
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
                   content: args.MESSAGE = None,
                   streaming: args.STREAMING = False) -> dict:
    """Send a message to an existing AI HelpDesk ticket.

    The ticket's assigned agent is fetched to decide whether to use the
    streaming endpoint; ``--streaming`` forces it on regardless.

    Usage: CLI Usage
      ```sh
      echo "the message" | duploctl ticket send_message --id <id> -W <workspace> -f -
      duploctl ticket send_message --id <id> -W <workspace> --content "the message"
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.
      content: The message text. Pass it inline with ``--content`` or
        read from stdin with ``-f -``.
      streaming: Force the streaming send endpoint.

    Returns:
      chat_response: A dict with ``ai_response`` and ``chat_url`` keys.

    Raises:
      DuploError: If no ticket identifier, workspace, or message is
        provided.
    """
    identifier = id or name
    if not identifier:
      raise DuploError("Either a ticket name or --id is required")
    if not content or not content.strip():
      raise DuploError(
          "Message content is required (pass --content or pipe with -f -).")
    workspace_id = self.workspace_id
    agent_id = self._agent_id_from_ticket(workspace_id, identifier)
    return self._dispatch_message(
        workspace_id=workspace_id,
        ticket_id=identifier,
        content=content,
        agent_id=agent_id,
        streaming=streaming,
    )

  def _agent_id_from_ticket(self,
                            workspace_id: str,
                            ticket_id: str) -> str:
    """Fetch the ticket and return its assigned ``aiAgentId``."""
    response = self.client.get(
        f"tickets/{workspace_id}/{ticket_id}").json()
    ticket = unwrap_data(response)
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
                        streaming: bool) -> dict:
    """Send a message, choosing the streaming or unary endpoint.

    Streaming is used when ``--streaming`` is set or when the assigned
    agent advertises ``metaData.STREAMING_ENABLED``. The helpdesk's
    non-streaming deserializer chokes on the NDJSON a streaming agent
    emits, so honoring the agent's own flag keeps the call correct even
    without ``--streaming``.
    """
    use_streaming = streaming or self.__agent_svc.supports_streaming(
        id=agent_id)
    send = self._send_streaming if use_streaming else self._send_unary
    ai_response = send(workspace_id, ticket_id, content)
    return {
      "ai_response": ai_response,
      "chat_url": self._chat_url(workspace_id, ticket_id),
    }

  def _send_unary(self,
                  workspace_id: str,
                  ticket_id: str,
                  content: str) -> dict:
    """POST to the unary sendMessage endpoint and return the JSON reply.

    A unary agent returns a single JSON object. If the agent actually
    streams (its ``metaData.STREAMING_ENABLED`` flag is stale, so the unary
    endpoint was chosen by mistake), the helpdesk's unary serializer can't
    parse the agent's NDJSON and returns a 400 whose body still embeds the
    reply events. Recover the reply from that body rather than surfacing the
    raw backend deserialization error.
    """
    path = f"tickets/{workspace_id}/{ticket_id}/sendMessage"
    try:
      return self.client.post(path, self._message_payload(content)).json()
    except DuploError as err:
      recovered = self._recover_streamed_reply(err)
      if recovered is not None:
        return recovered
      raise

  def _recover_streamed_reply(self, error: DuploError):
    """Recover an assistant reply embedded in a unary-send error body.

    When a streaming agent is hit on the unary endpoint the agent still
    answers, but the helpdesk returns its NDJSON inside the (JSON-encoded)
    error body. Assemble the events out of it. Returns None when the body
    isn't that recognizable shape, so genuine errors propagate unchanged.
    """
    body = error.args[0] if error.args else None
    if not isinstance(body, str):
      return None
    try:
      body = json.loads(body)  # the backend body is a JSON-encoded string
    except (ValueError, json.JSONDecodeError):
      pass
    if not isinstance(body, str):
      return None
    assembled = self._assemble_stream(body.splitlines())
    return assembled if assembled["content"] else None

  def _send_streaming(self,
                      workspace_id: str,
                      ticket_id: str,
                      content: str) -> dict:
    """POST to the SSE sendMessageStreaming endpoint and assemble the reply.

    Routes through the helpdesk client's ``post(..., stream=True)`` so URL
    construction, auth header injection, timeout, exception translation,
    and status validation are identical to the unary call — the
    streaming transport is the only difference.
    """
    path = f"tickets/{workspace_id}/{ticket_id}/sendMessageStreaming"
    with self.client.post(
        path, self._message_payload(content),
        headers={"Accept": "text/event-stream"}, stream=True,
    ) as resp:
      return self._assemble_stream(resp.iter_lines(decode_unicode=True))

  def _assemble_stream(self, lines) -> dict:
    """Assemble an agent reply from event lines (SSE ``data:`` or NDJSON).

    Concatenates ``text_delta`` chunks, raises on an ``error`` event, and
    stops at ``done``. Non-event lines — blanks, a backend error prefix,
    anything not a JSON object — are skipped, so a stray wrapper around
    otherwise-valid events doesn't lose the reply.
    """
    text_parts: list[str] = []
    raw_events: list[dict] = []
    for raw_line in lines:
      if not raw_line:
        continue
      line = raw_line.strip()
      if line.startswith("data:"):
        line = line[len("data:"):].strip()
      if not line.startswith("{"):
        continue
      try:
        event = json.loads(line)
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
  def list(self) -> list:
    """List the tickets in the AI HelpDesk workspace.

    Usage: CLI Usage
      ```sh
      duploctl ticket list -W <workspace>
      duploctl ticket list --workspace-id <workspace id>
      ```

    Returns:
      list: The tickets in the workspace.
    """
    response = self.client.get(f"tickets/{self.workspace_id}").json()
    if isinstance(response, dict):
      data = response.get("data", response)
      return data.get("items", data) if isinstance(data, dict) else data
    return response

  @Command()
  def assignee(self,
               name: args.NAME = None,
               id: args.ID = None) -> dict:
    """Get the agent currently assigned to a ticket.

    Usage: CLI Usage
      ```sh
      duploctl ticket assignee <name> -W <workspace>
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.

    Returns:
      resource: The assigned agent object.

    Raises:
      DuploError: If no ticket identifier is given.
    """
    identifier = id or name
    if not identifier:
      raise DuploError("Either a ticket name or --id is required")
    response = self.client.get(
        f"tickets/{self.workspace_id}/"
        f"{quote_plus(identifier)}/assignee").json()
    return unwrap_data(response)

  @Command()
  def reassign(self,
               name: args.NAME = None,
               id: args.ID = None,
               agent_name: args.AGENTNAME = None,
               agent_id: args.AGENTID = None) -> dict:
    """Reassign a ticket to a different agent.

    The agent is resolved by name or id via the ``agent`` resource.

    Usage: CLI Usage
      ```sh
      duploctl ticket reassign <name> -W <workspace> --agent <agent>
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.
      agent_name: The agent name to assign.
      agent_id: The agent id to assign. Skips the agent name lookup.

    Returns:
      message: A success message.

    Raises:
      DuploError: If no ticket identifier is given.
      DuploNotFound: If the agent cannot be found.
    """
    identifier = id or name
    if not identifier:
      raise DuploError("Either a ticket name or --id is required")
    aid = self.__agent_svc.find(name=agent_name, id=agent_id)["id"]
    self.client.put(
        f"tickets/{self.workspace_id}/"
        f"{quote_plus(identifier)}/assignee/{quote_plus(aid)}")
    return {"message": f"ticket '{identifier}' reassigned to agent "
                       f"'{agent_name or agent_id}'"}

  @Command()
  def set_status(self,
                 name: args.NAME = None,
                 id: args.ID = None,
                 status: args.TICKET_STATUS = None,
                 disposition: args.TICKET_DISPOSITION = None) -> dict:
    """Set a ticket's status.

    When ``--status closed`` is used, ``--disposition`` (``resolved`` or
    ``unResolved``) is required by the backend.

    Usage: CLI Usage
      ```sh
      duploctl ticket set_status <name> -W <workspace> --status inProgress
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.
      status: The new status (open, inProgress, waitingForUserInput,
        waitingForUserAgent, closed).
      disposition: The disposition (resolved, unResolved); required when
        closing.

    Returns:
      resource: The updated ticket object.

    Raises:
      DuploError: If no ticket identifier or status is given.
    """
    identifier = id or name
    if not identifier:
      raise DuploError("Either a ticket name or --id is required")
    if not status:
      raise DuploError("--status is required")
    # The backend requires a disposition when closing a ticket; enforce the
    # documented contract here so the user gets a clear error instead of a
    # backend rejection (matches close(), which always supplies one).
    if status == "closed" and not disposition:
      raise DuploError(
          "--disposition (resolved|unResolved) is required when closing "
          "a ticket")
    body = {"status": status}
    if disposition:
      body["disposition"] = disposition
    response = self.client.put(
        f"tickets/{self.workspace_id}/"
        f"{quote_plus(identifier)}/status", body).json()
    return unwrap_data(response)

  @Command()
  def close(self,
            name: args.NAME = None,
            id: args.ID = None,
            disposition: args.TICKET_DISPOSITION = "resolved") -> dict:
    """Close a ticket.

    Convenience wrapper for ``set_status --status closed``. The backend
    requires a disposition when closing; defaults to ``resolved``.

    Usage: CLI Usage
      ```sh
      duploctl ticket close <name> -W <workspace>
      duploctl ticket close <name> -W <workspace> --disposition unResolved
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.
      disposition: The disposition (resolved, unResolved). Defaults to
        resolved.

    Returns:
      resource: The updated ticket object.
    """
    # The CLI passes disposition=None when --disposition is omitted (argparse
    # uses args.TICKET_DISPOSITION's default of None, not this signature's
    # default), so coerce here — the backend requires a disposition on close.
    return self.set_status(
        name=name, id=id, status="closed",
        disposition=disposition or "resolved")

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Delete an AI HelpDesk ticket from the workspace.

    Usage: CLI Usage
      ```sh
      duploctl ticket delete <name> -W <workspace>
      duploctl ticket delete --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The ticket name/identifier (e.g. ``DEVOPS-42``).
      id: The ticket id. Used instead of name when provided.

    Returns:
      message: A success message.

    Raises:
      DuploError: If no ticket identifier is given.
    """
    identifier = id or name
    if not identifier:
      raise DuploError("Either a ticket name or --id is required")
    self.client.delete(
        f"tickets/{self.workspace_id}/{quote_plus(identifier)}")
    return {"message": f"ticket '{identifier}' deleted"}
