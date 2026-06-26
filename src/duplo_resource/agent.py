from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("agent", scope="tenant")
class DuploAgent(DuploResource):
  """Manage AI HelpDesk agents in DuploCloud.

  An agent processes AI HelpDesk tickets. Agents are resolved by name
  to their id for ticket assignment, and expose whether they stream
  responses via their ``metaData.STREAMING_ENABLED`` flag.
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo, api_version="v1")

  def _items(self, response: dict) -> list:
    """Unwrap a list envelope ``{success, data: {items: [...]}}``."""
    return response.get("data", {}).get("items", [])

  def _data(self, response: dict) -> dict:
    """Unwrap a single-object envelope ``{success, data: {...}}``."""
    data = response.get("data")
    return data if isinstance(data, dict) else response

  @Command("ls")
  def list(self, api_version: args.APIVERSION = "v1") -> list:
    """Retrieve a list of AI HelpDesk agents.

    Usage: CLI Usage
      ```sh
      duploctl agent list
      ```

    Args:
      api_version: Helpdesk API version.

    Returns:
      list: A list of agent objects.
    """
    api_version = api_version.strip().lower()
    response = self.client.get(
        f"{api_version}/aiservicedesk/admin/data/aiagents").json()
    return self._items(response)

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None,
           api_version: args.APIVERSION = "v1") -> dict:
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
      api_version: Helpdesk API version.

    Returns:
      resource: The matching agent object.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no agent matches the name or id.
    """
    api_version = api_version.strip().lower()
    base = f"{api_version}/aiservicedesk/admin/data/aiagents"
    if id:
      agent = self._data(self.client.get(f"{base}/{quote_plus(id)}").json())
      if not agent.get("id"):
        raise DuploNotFound(id, self.kind)
      return agent

    if not name:
      raise DuploError("Either an agent name or --id is required")

    response = self.client.get(
        f"{base}?filters[name]={quote_plus(name)}").json()
    target = name.lower()
    match = next((a for a in self._items(response)
                  if (a.get("name") or "").lower() == target), None)
    if not match:
      raise DuploNotFound(name, self.kind)
    return match

  @Command()
  def supports_streaming(self,
                         name: args.NAME = None,
                         id: args.ID = None,
                         api_version: args.APIVERSION = "v1") -> bool:
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
      api_version: Helpdesk API version.

    Returns:
      bool: True when ``metaData.STREAMING_ENABLED`` is ``"true"``.
    """
    agent = self.find(name=name, id=id, api_version=api_version)
    metadata = agent.get("metaData") or {}
    enabled = str(metadata.get("STREAMING_ENABLED", "")).strip().lower()
    return enabled == "true"
