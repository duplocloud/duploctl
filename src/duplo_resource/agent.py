from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
from duplo_resource.helpdesk_client import unwrap_data
import duplocloud.args as args


@Resource("agent", scope="portal", client="helpdesk")
class DuploAgent(DuploResource):
  """Manage AI HelpDesk agents in DuploCloud.

  An agent processes AI HelpDesk tickets. Agents are resolved by name
  to their id for ticket assignment, and expose whether they stream
  responses via their ``metaData.STREAMING_ENABLED`` flag.
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)

  @Command("ls")
  def list(self) -> list:
    """Retrieve a list of AI HelpDesk agents.

    Usage: CLI Usage
      ```sh
      duploctl agent list
      ```

    Returns:
      list: A list of agent objects.
    """
    return self.client.get_items("admin/data/aiagents")

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None) -> dict:
    """Find an AI HelpDesk agent by name or id.

    With ``--id`` the agent is fetched directly. Otherwise it is matched
    by name (case-insensitive) from the agents list. The list and
    single-agent endpoints return the same object shape, so the matching
    list entry — including ``metaData`` — is returned as-is.

    Usage: CLI Usage
      ```sh
      duploctl agent find <name>
      duploctl agent find --id <id>
      ```

    Args:
      name: The agent name as shown in the portal.
      id: The agent id. Skips the name lookup when provided.

    Returns:
      resource: The matching agent object.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no agent matches the name or id.
    """
    if id:
      agent = unwrap_data(
          self.client.get(f"admin/data/aiagents/{quote_plus(id)}").json())
      if not agent.get("id"):
        raise DuploNotFound(id, self.kind)
      return agent

    if not name:
      raise DuploError("Either an agent name or --id is required")

    items = self.client.get_items(
        f"admin/data/aiagents?filters[name]={quote_plus(name)}")
    target = name.lower()
    match = next((a for a in items
                  if (a.get("name") or "").lower() == target), None)
    if not match:
      raise DuploNotFound(name, self.kind)
    return match

  @Command()
  def supports_streaming(self,
                         name: args.NAME = None,
                         id: args.ID = None) -> bool:
    """Return whether an agent streams its responses.

    The top-level ``doesSupportStreaming`` is unreliable on some portals
    — agents that actually stream still report ``false``. The
    authoritative flag is ``metaData.STREAMING_ENABLED`` (the string
    ``"true"``), which this command reads.

    Usage: CLI Usage
      ```sh
      duploctl agent supports_streaming <name>
      duploctl agent supports_streaming --id <id>
      ```

    Args:
      name: The agent name as shown in the portal.
      id: The agent id. Skips the name lookup when provided.

    Returns:
      bool: True when ``metaData.STREAMING_ENABLED`` is ``"true"``.
    """
    agent = self.find(name=name, id=id)
    metadata = agent.get("metaData") or {}
    enabled = str(metadata.get("STREAMING_ENABLED", "")).strip().lower()
    return enabled == "true"

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Delete an AI HelpDesk agent by name or id.

    Usage: CLI Usage
      ```sh
      duploctl agent delete <name>
      duploctl agent delete --id <id>
      ```

    Args:
      name: The agent name as shown in the portal.
      id: The agent id. Skips the name lookup when provided.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If no agent matches the name or id.
    """
    aid = self.find(name=name, id=id)["id"]
    self.client.delete(f"admin/data/aiagents/{quote_plus(aid)}")
    return {"message": f"agent '{name or id}' deleted"}

  @Command()
  def create(self, body: args.BODY) -> dict:
    """Create an AI HelpDesk agent.

    Usage: CLI Usage
      ```sh
      duploctl agent create -f agent.yaml
      ```

    Args:
      body: The agent definition.

    Returns:
      resource: The created agent object.
    """
    response = self.client.post("admin/data/aiagents", body).json()
    return unwrap_data(response)

  @Command()
  def update(self,
             body: args.BODY = None,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Update an AI HelpDesk agent.

    The target is resolved by ``--id``, ``name``, or the body's ``name``
    field, in that order. The update is a full replace — fields omitted
    from the body are cleared — and the name is immutable, so a body
    whose ``name`` differs from the stored record is rejected by the
    backend.

    Usage: CLI Usage
      ```sh
      duploctl agent update <name> -f agent.yaml
      duploctl agent update -f agent.yaml
      ```

    Args:
      body: The agent definition to apply.
      name: The agent name. Defaults to the body's ``name``.
      id: The agent id. Skips the name lookup when provided.

    Returns:
      resource: The updated agent object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the agent cannot be found.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    aid = self.find(name=name or body.get("name"), id=id)["id"]
    response = self.client.put(
        f"admin/data/aiagents/{quote_plus(aid)}", body).json()
    return unwrap_data(response)

  @Command()
  def apply(self, body: args.BODY) -> dict:
    """Create or update an AI HelpDesk agent.

    Looks the agent up by the body's ``name``: updates it when it exists,
    creates it otherwise.

    Usage: CLI Usage
      ```sh
      duploctl agent apply -f agent.yaml
      ```

    Args:
      body: The agent definition to apply.

    Returns:
      resource: The created or updated agent object.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    try:
      self.find(name=body.get("name"))
    except DuploNotFound:
      return self.create(body=body)
    return self.update(body=body)
