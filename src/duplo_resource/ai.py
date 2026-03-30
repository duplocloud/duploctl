import json

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("ai", scope="tenant")
class DuploAI(DuploResourceV3):
  """Resource for the DuploCloud AI Service Desk.

  Provides commands for managing workspaces, projects, tickets, specs,
  and plans in the DuploCloud AI HelpDesk.
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo, "")  # No static endpoint; we build it dynamically

  @staticmethod
  def _parse_ticket_response(response) -> dict:
    """Parse a ticket API response that may be JSON or NDJSON streaming.

    The AI Service Desk may return a single JSON object or a stream of
    newline-delimited JSON chunks (NDJSON). This method handles both.

    Args:
      response: The HTTP response object.

    Returns:
      The parsed response as a dictionary.
    """
    text = response.text.strip()
    try:
      return response.json()
    except (json.JSONDecodeError, ValueError):
      pass

    # Try NDJSON: concatenate text_delta chunks, extract ticket info
    ai_text_parts = []
    ticket_info = {}
    for line in text.splitlines():
      line = line.strip()
      if not line:
        continue
      try:
        chunk = json.loads(line)
      except (json.JSONDecodeError, ValueError):
        continue
      chunk_type = chunk.get("type", "")
      if chunk_type == "text_delta":
        ai_text_parts.append(chunk.get("text", ""))
      elif chunk_type == "executed_tool_calls":
        for call in chunk.get("executed_tool_calls", []):
          if call.get("name") == "session_saved":
            session_id = call.get("input", {}).get("session_id", "")
            if session_id:
              ticket_info["session_id"] = session_id

    return {
      "ticket": ticket_info,
      "message": "".join(ai_text_parts) if ai_text_parts else None,
    }

  # ------------------------------------------------------------------
  # Workspace commands
  # ------------------------------------------------------------------

  @Command()
  def list_workspaces(self,
                      api_version: args.APIVERSION = "v1") -> list:
    """List AI Service Desk workspaces.

    List all available workspaces in the AI Service Desk.
    This is a portal-level call and does not require a tenant.

    Usage:
      ```sh
      duploctl ai list_workspaces
      ```

    Returns:
      workspaces: A list of workspace objects with id and name.
    """
    api_version = api_version.strip().lower()
    path = f"{api_version}/aiservicedesk/admin/data/workspaces"
    response = self.client.get(path)
    return response.json()

  # ------------------------------------------------------------------
  # Project commands
  # ------------------------------------------------------------------

  @Command()
  def list_projects(self,
                    api_version: args.APIVERSION = "v1") -> list:
    """List AI Service Desk projects.

    List all projects in the current workspace (tenant).

    Usage:
      ```sh
      duploctl ai list_projects -T <workspace>
      ```

    Returns:
      projects: A list of project objects.
    """
    api_version = api_version.strip().lower()
    tenant_id = self.tenant_id
    path = (
      f"{api_version}/aiservicedesk/user/data/projects"
      f"?filters[workspaceId]={tenant_id}"
    )
    response = self.client.get(path)
    return response.json()

  @Command()
  def get_project(self,
                  project_id: args.PROJECTID,
                  api_version: args.APIVERSION = "v1") -> dict:
    """Get AI Service Desk project details.

    Fetch full project details including spec, plan, and execution tasks.

    Usage:
      ```sh
      duploctl ai get_project --project-id <id>
      ```

    Args:
      project_id: The project ID.
      api_version: Helpdesk API version.

    Returns:
      project: The full project object with spec, plan, and tasks.
    """
    api_version = api_version.strip().lower()
    path = f"{api_version}/aiservicedesk/user/data/projects/{project_id}"
    response = self.client.get(path)
    return response.json()

  @Command()
  def save_spec(self,
                project_id: args.PROJECTID,
                artifact_content: args.ARTIFACT_CONTENT,
                approve: args.APPROVE = False,
                api_version: args.APIVERSION = "v1") -> dict:
    """Save project spec.

    Save spec content to a project, optionally approving it.

    Usage:
      ```sh
      duploctl ai save_spec --project-id <id> --artifact-content "# Spec" [--approve]
      ```

    Args:
      project_id: The project ID.
      artifact_content: The spec content (markdown).
      approve: If set, mark the spec as Approved.
      api_version: Helpdesk API version.

    Returns:
      message: Confirmation of the save operation.
    """
    api_version = api_version.strip().lower()
    path = f"{api_version}/aiservicedesk/user/data/projects/{project_id}"

    # Fetch current project to preserve other fields
    response = self.client.get(path)
    project = response.json()
    if isinstance(project, dict) and "data" in project:
      project = project["data"]

    spec = project.get("spec", {}) or {}
    spec["content"] = artifact_content
    if approve:
      meta = spec.get("metaData", {}) or {}
      meta["approvalState"] = "Approved"
      spec["metaData"] = meta
    project["spec"] = spec

    self.client.put(path, project)
    status = "saved and approved" if approve else "saved"
    return {"message": f"Spec {status}", "project_id": project_id}

  @Command()
  def save_plan(self,
                project_id: args.PROJECTID,
                artifact_content: args.ARTIFACT_CONTENT,
                approve: args.APPROVE = False,
                api_version: args.APIVERSION = "v1") -> dict:
    """Save project plan.

    Save plan content to a project, optionally approving it.

    Usage:
      ```sh
      duploctl ai save_plan --project-id <id> --artifact-content "# Plan" [--approve]
      ```

    Args:
      project_id: The project ID.
      artifact_content: The plan content (markdown).
      approve: If set, mark the plan as Approved.
      api_version: Helpdesk API version.

    Returns:
      message: Confirmation of the save operation.
    """
    api_version = api_version.strip().lower()
    path = f"{api_version}/aiservicedesk/user/data/projects/{project_id}"

    response = self.client.get(path)
    project = response.json()
    if isinstance(project, dict) and "data" in project:
      project = project["data"]

    plan = project.get("plan", {}) or {}
    plan["content"] = artifact_content
    if approve:
      meta = plan.get("metaData", {}) or {}
      meta["approvalState"] = "Approved"
      plan["metaData"] = meta
    project["plan"] = plan

    self.client.put(path, project)
    status = "saved and approved" if approve else "saved"
    return {"message": f"Plan {status}", "project_id": project_id}

  # ------------------------------------------------------------------
  # Agent commands
  # ------------------------------------------------------------------

  @Command()
  def list_agents(self,
                  api_version: args.APIVERSION = "v1") -> list:
    """List AI agents.

    List AI agents available in the current workspace (tenant).

    Usage:
      ```sh
      duploctl ai list_agents -T <workspace>
      ```

    Returns:
      agents: A list of agent objects with id and name.
    """
    api_version = api_version.strip().lower()
    tenant_id = self.tenant_id
    path = (
      f"{api_version}/aiservicedesk/user/data"
      f"/workspaces/{tenant_id}/agents"
    )
    response = self.client.get(path)
    return response.json()

  # ------------------------------------------------------------------
  # Ticket commands
  # ------------------------------------------------------------------

  @Command()
  def list_tickets(self,
                   project_id: args.PROJECTID,
                   ticket_type: args.TICKETTYPE = "spec_creation",
                   api_version: args.APIVERSION = "v1") -> list:
    """List AI Service Desk tickets.

    List tickets for a project filtered by type.

    Usage:
      ```sh
      duploctl ai list_tickets -T <workspace> --project-id <id> [--ticket-type plan_execution]
      ```

    Args:
      project_id: The project ID.
      ticket_type: The ticket type: spec_creation (0) or plan_execution (2).
      api_version: Helpdesk API version.

    Returns:
      tickets: A list of ticket objects.
    """
    api_version = api_version.strip().lower()
    tenant_id = self.tenant_id
    project_type = 0 if ticket_type == "spec_creation" else 2
    path = (
      f"{api_version}/aiservicedesk/tickets/{tenant_id}"
      f"?projectId={project_id}&projectType={project_type}"
    )
    response = self.client.get(path)
    return response.json()

  @Command()
  def get_ticket(self,
                 ticket_ref: args.TICKETREF,
                 api_version: args.APIVERSION = "v1") -> dict:
    """Get AI Service Desk ticket.

    Fetch a single ticket by its ID or name.

    Usage:
      ```sh
      duploctl ai get_ticket -T <workspace> --ticket-ref <id-or-name>
      ```

    Args:
      ticket_ref: The ticket ID or name.
      api_version: Helpdesk API version.

    Returns:
      ticket: The ticket object.
    """
    api_version = api_version.strip().lower()
    tenant_id = self.tenant_id
    path = (
      f"{api_version}/aiservicedesk/tickets/{tenant_id}/{ticket_ref}"
    )
    response = self.client.get(path)
    return response.json()

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
      "aiAgentId": instance_id,
      "assignee": {
        "agentName": agent_name,
        "instanceId": instance_id
      },
      "Origin": helpdesk_origin if helpdesk_origin else "duploctl",
    }

    response = self.client.post(path, payload)
    data = response.json()
    ticket = data.get("ticket", {})
    ticket_name = ticket.get("name")

    if not ticket_name or ticket_name == "null":
      raise DuploError(
        "Could not extract ticket name from response.\n"
        f"Full response: {response.text}"
      )

    result = {
      "ticketname": ticket_name,
      "chat_url": f"{self.duplo.host}/app/ai/service-desk/{tenant_id}/tickets/chat/{ticket_name}",
      "ai_response": None,
    }

    # Send the initial message separately to avoid streaming response issues
    if content:
      msg = self.send_message(
        ticket_id=ticket_name, content=content,
        api_version=api_version,
      )
      result["ai_response"] = msg.get("ai_response")

    return result

  @Command()
  def create_project_ticket(self,
                            project_id: args.PROJECTID,
                            agent_id: args.AGENTID,
                            ticket_type: args.TICKETTYPE = "spec_creation",
                            project_name: args.PROJECTNAME = None,
                            api_version: args.APIVERSION = "v1") -> dict:
    """Create AI Service Desk project ticket.

    Create a spec or execution ticket linked to a project.

    Usage:
      ```sh
      duploctl ai create_project_ticket -T <workspace> \\
        --project-id <id> --agent-id <agent> [--ticket-type plan_execution]
      ```

    Args:
      project_id: The project ID.
      agent_id: The AI agent ID to assign.
      ticket_type: The ticket type: spec_creation or plan_execution.
      project_name: The project name (used in ticket title).
      api_version: Helpdesk API version.

    Returns:
      ticket: The created ticket object.
    """
    api_version = api_version.strip().lower()
    tenant_id = self.tenant_id
    type_code = 0 if ticket_type == "spec_creation" else 2
    suffix = "Spec-Creation" if type_code == 0 else "Plan-Execution"
    title = f"{project_name or project_id}-{suffix}-Ticket"

    payload = {
      "title": title,
      "aiAgentId": agent_id,
      "project": {"id": project_id, "type": type_code},
      "ticketContextForAgent": {"scopeIds": []},
      "tenantId": tenant_id,
      "platform_context": {
        "duplo_base_url": self.duplo.host,
        "duplo_token": self.duplo.token,
        "project": {"id": project_id, "type": type_code},
      },
    }

    path = f"{api_version}/aiservicedesk/tickets/{tenant_id}"
    response = self.client.post(path, payload)
    return response.json()

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

    try:
      response = self.client.post(path, payload)
      result = response.json()
    except DuploError as e:
      # The AI agent may return a streaming NDJSON response that the
      # server wraps in a 500 error. Parse the AI text from the error.
      result = self._parse_streaming_error(str(e))

    return {
      "ai_response": result,
      "chat_url": f"{self.duplo.host}/app/ai/service-desk/{tenant_id}/tickets/chat/{ticket_id}"
    }

  @staticmethod
  def _parse_streaming_error(error_text: str) -> str:
    """Extract AI response text from a streaming NDJSON error message.

    When the AI agent streams its response, the server may fail to
    serialize it and return a 500 with NDJSON chunks in the error body.
    This method extracts the text_delta content.

    The error format is typically:
      Duplo responded with (500): "Error {json}\\n{json}\\n..."

    Args:
      error_text: The error message string.

    Returns:
      The concatenated AI response text, or the raw error.
    """
    # Strip the DuploError wrapper to get the raw NDJSON body.
    # The error may contain \\u0022 (escaped unicode quotes) and \\n
    # (escaped newlines) that need to be decoded first.
    body = error_text
    body = body.encode().decode("unicode_escape", errors="replace")

    # Find start of the NDJSON content
    idx = body.find('{"type"')
    if idx == -1:
      return error_text
    body = body[idx:]
    # Trim trailing non-JSON suffix
    last_brace = body.rfind("}")
    if last_brace != -1:
      body = body[:last_brace + 1]

    parts = []
    for line in body.splitlines():
      line = line.strip()
      if not line:
        continue
      try:
        chunk = json.loads(line)
        if chunk.get("type") == "text_delta":
          parts.append(chunk.get("text", ""))
      except (json.JSONDecodeError, ValueError):
        continue
    return "".join(parts) if parts else error_text

  @Command()
  def mirror_message(self,
                     ticket_name: args.TICKETREF,
                     content: args.MESSAGE,
                     role: args.ROLE = "user",
                     api_version: args.APIVERSION = "v1") -> dict:
    """Mirror conversation message to a ticket.

    Send a mirrored conversation message to a ticket using the
    streaming endpoint. Used by hooks to sync Claude Code
    conversations with Service Desk tickets.

    Usage:
      ```sh
      duploctl ai mirror_message -T <workspace> \\
        --ticket-ref <ticket-name> --content "message" [--role assistant]
      ```

    Args:
      ticket_name: The ticket name (not ID).
      content: The message content.
      role: The message role: user or assistant.
      api_version: Helpdesk API version.

    Returns:
      message: Confirmation that the message was mirrored.
    """
    if not content or not content.strip():
      raise ValueError("The 'content' parameter is required and cannot be empty.")

    api_version = api_version.strip().lower()
    tenant_id = self.tenant_id

    path = (
      f"{api_version}/aiservicedesk/tickets"
      f"/{tenant_id}/{ticket_name}/sendmessageStreaming"
    )

    payload = {
      "content": content,
      "message_mode": 1,
      "data": {},
      "tenant_id": tenant_id,
      "role": role,
    }

    response = self.client.post(path, payload)
    return {"message": "Message mirrored", "role": role}
