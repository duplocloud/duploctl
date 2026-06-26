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
    self.__agent_svc = self.duplo.load("agent")

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

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None,
             api_version: args.APIVERSION = "v1") -> dict:
    """Delete an AI HelpDesk workspace by name or id.

    Usage: CLI Usage
      ```sh
      duploctl workspace delete <name>
      duploctl workspace delete --id <id>
      ```

    Args:
      name: The workspace name as shown in the portal.
      id: The workspace id. Skips the name lookup when provided.
      api_version: Helpdesk API version.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If no workspace matches the name or id.
    """
    api_version = api_version.strip().lower()
    wid = self.find(name=name, id=id, api_version=api_version)["id"]
    self.client.delete(
        f"{api_version}/aiservicedesk/admin/data/workspaces/"
        f"{quote_plus(wid)}")
    return {"message": f"workspace '{name or id}' deleted"}

  @Command()
  def add_agent(self,
                name: args.NAME = None,
                id: args.ID = None,
                agent_name: args.AGENTNAME = None,
                agent_id: args.AGENTID = None,
                api_version: args.APIVERSION = "v1") -> dict:
    """Add an AI agent to a workspace.

    The workspace and agent are each resolved by name or id via their
    respective `find` commands.

    Usage: CLI Usage
      ```sh
      duploctl workspace add_agent <name> --agent <agent name>
      duploctl workspace add_agent --id <id> --agent_id <agent id>
      ```

    Args:
      name: The workspace name.
      id: The workspace id. Skips the workspace name lookup.
      agent_name: The agent name to add.
      agent_id: The agent id to add. Skips the agent name lookup.
      api_version: Helpdesk API version.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If the workspace or agent cannot be found.
    """
    api_version = api_version.strip().lower()
    wid = self.find(name=name, id=id, api_version=api_version)["id"]
    aid = self.__agent_svc.find(
        name=agent_name, id=agent_id, api_version=api_version)["id"]
    self.client.post(
        f"{api_version}/aiservicedesk/admin/data/workspaces/"
        f"{quote_plus(wid)}/agents/{quote_plus(aid)}")
    return {"message": f"agent '{agent_name or agent_id}' added to "
                       f"workspace '{name or id}'"}

  @Command()
  def remove_agent(self,
                   name: args.NAME = None,
                   id: args.ID = None,
                   agent_name: args.AGENTNAME = None,
                   agent_id: args.AGENTID = None,
                   api_version: args.APIVERSION = "v1") -> dict:
    """Remove an AI agent from a workspace.

    The workspace and agent are each resolved by name or id via their
    respective `find` commands.

    Usage: CLI Usage
      ```sh
      duploctl workspace remove_agent <name> --agent <agent name>
      duploctl workspace remove_agent --id <id> --agent_id <agent id>
      ```

    Args:
      name: The workspace name.
      id: The workspace id. Skips the workspace name lookup.
      agent_name: The agent name to remove.
      agent_id: The agent id to remove. Skips the agent name lookup.
      api_version: Helpdesk API version.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If the workspace or agent cannot be found.
    """
    api_version = api_version.strip().lower()
    wid = self.find(name=name, id=id, api_version=api_version)["id"]
    aid = self.__agent_svc.find(
        name=agent_name, id=agent_id, api_version=api_version)["id"]
    self.client.delete(
        f"{api_version}/aiservicedesk/admin/data/workspaces/"
        f"{quote_plus(wid)}/agents/{quote_plus(aid)}")
    return {"message": f"agent '{agent_name or agent_id}' removed from "
                       f"workspace '{name or id}'"}

  @Command()
  def create(self,
             body: args.BODY,
             api_version: args.APIVERSION = "v1") -> dict:
    """Create an AI HelpDesk workspace.

    Usage: CLI Usage
      ```sh
      duploctl workspace create -f workspace.yaml
      ```

    Args:
      body: The workspace definition.
      api_version: Helpdesk API version.

    Returns:
      resource: The created workspace object.
    """
    api_version = api_version.strip().lower()
    response = self.client.post(
        f"{api_version}/aiservicedesk/admin/data/workspaces", body).json()
    return self._data(response)

  @Command()
  def update(self,
             body: args.BODY = None,
             name: args.NAME = None,
             id: args.ID = None,
             api_version: args.APIVERSION = "v1") -> dict:
    """Update an AI HelpDesk workspace.

    The target is resolved by ``--id``, ``name``, or the body's ``name``
    field, in that order.

    Usage: CLI Usage
      ```sh
      duploctl workspace update <name> -f workspace.yaml
      duploctl workspace update -f workspace.yaml
      ```

    Args:
      body: The workspace definition to apply.
      name: The workspace name. Defaults to the body's ``name``.
      id: The workspace id. Skips the name lookup when provided.
      api_version: Helpdesk API version.

    Returns:
      resource: The updated workspace object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the workspace cannot be found.
    """
    api_version = api_version.strip().lower()
    if not body:
      raise DuploError("A request body (-f) is required")
    wid = self.find(
        name=name or body.get("name"), id=id, api_version=api_version)["id"]
    # The backend's name-uniqueness check excludes the record being updated
    # only when the body carries its id; without it the PUT is rejected as a
    # name collision with itself.
    body = {**body, "id": wid}
    response = self.client.put(
        f"{api_version}/aiservicedesk/admin/data/workspaces/"
        f"{quote_plus(wid)}", body).json()
    return self._data(response)

  @Command()
  def apply(self,
            body: args.BODY,
            api_version: args.APIVERSION = "v1") -> dict:
    """Create or update an AI HelpDesk workspace.

    Looks the workspace up by the body's ``name``: updates it when it
    exists, creates it otherwise.

    Usage: CLI Usage
      ```sh
      duploctl workspace apply -f workspace.yaml
      ```

    Args:
      body: The workspace definition to apply.
      api_version: Helpdesk API version.

    Returns:
      resource: The created or updated workspace object.
    """
    api_version = api_version.strip().lower()
    try:
      self.find(name=body.get("name"), api_version=api_version)
    except DuploNotFound:
      return self.create(body=body, api_version=api_version)
    return self.update(body=body, api_version=api_version)
