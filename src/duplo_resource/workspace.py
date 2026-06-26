from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("workspace", scope="tenant")
class DuploWorkspace(DuploResource):
  """Manage AI HelpDesk workspaces in DuploCloud.

  A workspace groups AI HelpDesk tickets and agents. Tickets are keyed
  on a workspace's 24-character Mongo ObjectId, which this resource
  resolves from the human-readable name shown in the portal.
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
    """Retrieve a list of AI HelpDesk workspaces.

    Usage: CLI Usage
      ```sh
      duploctl workspace list
      ```

    Args:
      api_version: Helpdesk API version.

    Returns:
      list: A list of workspace objects.
    """
    api_version = api_version.strip().lower()
    response = self.client.get(
        f"{api_version}/aiservicedesk/admin/data/workspaces").json()
    return self._items(response)

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None,
           api_version: args.APIVERSION = "v1") -> dict:
    """Find an AI HelpDesk workspace by name or id.

    With ``--id`` the workspace is fetched directly. Otherwise it is
    matched by name (case-insensitive) from the workspaces list.

    Usage: CLI Usage
      ```sh
      duploctl workspace find <name>
      duploctl workspace find --id <id>
      ```

    Args:
      name: The workspace name as shown in the portal.
      id: The workspace id. Skips the name lookup when provided.
      api_version: Helpdesk API version.

    Returns:
      resource: The matching workspace object.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no workspace matches the name or id.
    """
    api_version = api_version.strip().lower()
    base = f"{api_version}/aiservicedesk/admin/data/workspaces"
    if id:
      response = self.client.get(f"{base}/{quote_plus(id)}").json()
      workspace = self._data(response)
      if not workspace.get("id"):
        raise DuploNotFound(id, self.kind)
      return workspace

    if not name:
      raise DuploError("Either a workspace name or --id is required")

    response = self.client.get(
        f"{base}?filters[name]={quote_plus(name)}").json()
    target = name.lower()
    match = next((w for w in self._items(response)
                  if (w.get("name") or "").lower() == target), None)
    if not match:
      raise DuploNotFound(name, self.kind)
    return match
