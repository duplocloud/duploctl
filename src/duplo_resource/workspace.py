from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
from duplo_resource.helpdesk_client import unwrap_data
import duplocloud.args as args


@Resource("workspace", scope="portal", client="helpdesk")
class DuploWorkspace(DuploResource):
  """Manage AI HelpDesk workspaces in DuploCloud.

  A workspace groups AI HelpDesk tickets and agents. Tickets are keyed
  on a workspace's 24-character Mongo ObjectId, which this resource
  resolves from the human-readable name shown in the portal.
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)
    self.__agent_svc = self.duplo.load("agent")
    self.__scope_svc = None

  @property
  def _scope_svc(self):
    """Lazy-load the scope resource for the scope mapping commands."""
    if self.__scope_svc is None:
      self.__scope_svc = self.duplo.load("scope")
    return self.__scope_svc

  @Command("ls")
  def list(self) -> list:
    """Retrieve a list of AI HelpDesk workspaces.

    Usage: CLI Usage
      ```sh
      duploctl workspace list
      ```

    Returns:
      list: A list of workspace objects.
    """
    return self.client.get_items("admin/data/workspaces")

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None) -> dict:
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

    Returns:
      resource: The matching workspace object.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no workspace matches the name or id.
    """
    if id:
      response = self.client.get(
          f"admin/data/workspaces/{quote_plus(id)}").json()
      workspace = unwrap_data(response)
      if not workspace.get("id"):
        raise DuploNotFound(id, self.kind)
      return workspace

    if not name:
      raise DuploError(
          "A workspace is required: pass -W/--workspace, --workspace-id, "
          "or set DUPLO_WORKSPACE")

    items = self.client.get_items(
        f"admin/data/workspaces?filters[name]={quote_plus(name)}")
    target = name.lower()
    match = next((w for w in items
                  if (w.get("name") or "").lower() == target), None)
    if not match:
      raise DuploNotFound(name, self.kind)
    return match

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Delete an AI HelpDesk workspace by name or id.

    Usage: CLI Usage
      ```sh
      duploctl workspace delete <name>
      duploctl workspace delete --id <id>
      ```

    Args:
      name: The workspace name as shown in the portal.
      id: The workspace id. Skips the name lookup when provided.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If no workspace matches the name or id.
    """
    wid = self.find(name=name, id=id)["id"]
    self.client.delete(f"admin/data/workspaces/{quote_plus(wid)}")
    return {"message": f"workspace '{name or id}' deleted"}

  @Command()
  def add_agent(self,
                name: args.NAME = None,
                id: args.ID = None,
                agent_name: args.AGENTNAME = None,
                agent_id: args.AGENTID = None) -> dict:
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

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If the workspace or agent cannot be found.
    """
    wid = self.find(name=name, id=id)["id"]
    aid = self.__agent_svc.find(name=agent_name, id=agent_id)["id"]
    self.client.post(
        f"admin/data/workspaces/{quote_plus(wid)}/agents/{quote_plus(aid)}")
    return {"message": f"agent '{agent_name or agent_id}' added to "
                       f"workspace '{name or id}'"}

  @Command()
  def remove_agent(self,
                   name: args.NAME = None,
                   id: args.ID = None,
                   agent_name: args.AGENTNAME = None,
                   agent_id: args.AGENTID = None) -> dict:
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

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If the workspace or agent cannot be found.
    """
    wid = self.find(name=name, id=id)["id"]
    aid = self.__agent_svc.find(name=agent_name, id=agent_id)["id"]
    self.client.delete(
        f"admin/data/workspaces/{quote_plus(wid)}/agents/{quote_plus(aid)}")
    return {"message": f"agent '{agent_name or agent_id}' removed from "
                       f"workspace '{name or id}'"}

  @Command()
  def add_scope(self,
                name: args.NAME = None,
                id: args.ID = None,
                scope_name: args.SCOPENAME = None,
                scope_id: args.SCOPEID = None) -> dict:
    """Attach a scope to a workspace.

    The workspace and scope are each resolved by name or id via their
    respective `find` commands.

    Usage: CLI Usage
      ```sh
      duploctl workspace add_scope <name> --scope <scope name>
      duploctl workspace add_scope --id <id> --scope_id <scope id>
      ```

    Args:
      name: The workspace name.
      id: The workspace id. Skips the workspace name lookup.
      scope_name: The scope name to attach.
      scope_id: The scope id to attach. Skips the scope name lookup.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If the workspace or scope cannot be found.
    """
    wid = self.find(name=name, id=id)["id"]
    scope = self._scope_svc.find(name=scope_name, id=scope_id)
    sid = self._scope_svc._id_of(scope)
    self.client.post(
        f"admin/data/workspaces/{quote_plus(wid)}/scopes/{quote_plus(sid)}")
    return {"message": f"scope '{scope_name or scope_id}' added to "
                       f"workspace '{name or id}'"}

  @Command()
  def remove_scope(self,
                   name: args.NAME = None,
                   id: args.ID = None,
                   scope_name: args.SCOPENAME = None,
                   scope_id: args.SCOPEID = None) -> dict:
    """Detach a scope from a workspace.

    The workspace and scope are each resolved by name or id via their
    respective `find` commands.

    Usage: CLI Usage
      ```sh
      duploctl workspace remove_scope <name> --scope <scope name>
      duploctl workspace remove_scope --id <id> --scope_id <scope id>
      ```

    Args:
      name: The workspace name.
      id: The workspace id. Skips the workspace name lookup.
      scope_name: The scope name to detach.
      scope_id: The scope id to detach. Skips the scope name lookup.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If the workspace or scope cannot be found.
    """
    wid = self.find(name=name, id=id)["id"]
    scope = self._scope_svc.find(name=scope_name, id=scope_id)
    sid = self._scope_svc._id_of(scope)
    self.client.delete(
        f"admin/data/workspaces/{quote_plus(wid)}/scopes/{quote_plus(sid)}")
    return {"message": f"scope '{scope_name or scope_id}' removed from "
                       f"workspace '{name or id}'"}

  @Command()
  def create(self, body: args.BODY) -> dict:
    """Create an AI HelpDesk workspace.

    Usage: CLI Usage
      ```sh
      duploctl workspace create -f workspace.yaml
      ```

    Args:
      body: The workspace definition.

    Returns:
      resource: The created workspace object.
    """
    response = self.client.post("admin/data/workspaces", body).json()
    return unwrap_data(response)

  @Command()
  def update(self,
             body: args.BODY = None,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Update an AI HelpDesk workspace.

    The target is resolved by ``--id``, ``name``, or the body's ``name``
    field, in that order. The update is a full replace — fields omitted
    from the body are cleared — and the name is immutable, so a body
    whose ``name`` differs from the stored record is rejected by the
    backend.

    Usage: CLI Usage
      ```sh
      duploctl workspace update <name> -f workspace.yaml
      duploctl workspace update -f workspace.yaml
      ```

    Args:
      body: The workspace definition to apply.
      name: The workspace name. Defaults to the body's ``name``.
      id: The workspace id. Skips the name lookup when provided.

    Returns:
      resource: The updated workspace object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the workspace cannot be found.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    wid = self.find(name=name or body.get("name"), id=id)["id"]
    # admin PUTs must carry the record id in the body: the backend
    # deserializes into an entity whose id self-generates when absent,
    # making its uniqueness check collide with the record itself
    payload = {**body, "id": wid}
    response = self.client.put(
        f"admin/data/workspaces/{quote_plus(wid)}", payload).json()
    return unwrap_data(response)

  @Command()
  def apply(self, body: args.BODY) -> dict:
    """Create or update an AI HelpDesk workspace.

    Looks the workspace up by the body's ``name``: updates it when it
    exists, creates it otherwise.

    Usage: CLI Usage
      ```sh
      duploctl workspace apply -f workspace.yaml
      ```

    Args:
      body: The workspace definition to apply.

    Returns:
      resource: The created or updated workspace object.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    try:
      self.find(name=body.get("name"))
    except DuploNotFound:
      return self.create(body=body)
    return self.update(body=body)
