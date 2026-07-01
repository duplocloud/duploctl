from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("environment", scope="tenant")
class DuploEnvironment(DuploResource):
  """Manage AI HelpDesk (HDV2) environments in DuploCloud.

  An environment groups resource groups and their workloads inside a
  workspace. Environments are resolved by name to their id so the same
  name-or-id lookup is shared across the CLI; workspace resolution is
  delegated to the ``workspace`` resource.
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo, api_version="v1")
    self.__workspace_svc = self.duplo.load("workspace")

  def _items(self, response: dict) -> list:
    """Unwrap a paginated list envelope ``{data: {items: [...]}}``."""
    return response.get("data", {}).get("items", [])

  def _data(self, response: dict) -> dict:
    """Unwrap a single-object envelope ``{success, data: {...}}``."""
    data = response.get("data")
    return data if isinstance(data, dict) else response

  def _resolve_workspace_id(self,
                            workspace: str,
                            workspace_id: str,
                            api_version: str) -> str:
    """Resolve a workspace name/id to its id via the workspace resource."""
    return self.__workspace_svc.find(
        name=workspace, id=workspace_id, api_version=api_version)["id"]

  def _base(self, workspace_id: str, api_version: str) -> str:
    """Build the workspace-scoped environments endpoint."""
    return (f"{api_version}/aiservicedesk/user/data/workspaces/"
            f"{workspace_id}/environments")

  @Command("ls")
  def list(self,
           workspace: args.WORKSPACE = None,
           workspace_id: args.WORKSPACEID = None,
           api_version: args.APIVERSION = "v1") -> list:
    """Retrieve the environments in an AI HelpDesk workspace.

    Usage: CLI Usage
      ```sh
      duploctl environment list --workspace <workspace>
      duploctl environment list --workspace-id <workspace id>
      ```

    Args:
      workspace: The workspace name the environments belong to.
      workspace_id: The workspace id the environments belong to.
      api_version: Helpdesk API version.

    Returns:
      list: The environments in the workspace.
    """
    api_version = api_version.strip().lower()
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    response = self.client.get(self._base(wid, api_version)).json()
    return self._items(response)

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None,
           workspace: args.WORKSPACE = None,
           workspace_id: args.WORKSPACEID = None,
           api_version: args.APIVERSION = "v1") -> dict:
    """Find an AI HelpDesk environment by name or id within a workspace.

    With ``--id`` the environment is fetched directly. Otherwise it is
    matched by name (case-insensitive) from the workspace's environments.

    Usage: CLI Usage
      ```sh
      duploctl environment find <name> --workspace <workspace>
      duploctl environment find --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The environment name as shown in the portal.
      id: The environment id. Skips the name lookup when provided.
      workspace: The workspace name the environment belongs to.
      workspace_id: The workspace id the environment belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The matching environment object.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no environment matches the name or id.
    """
    api_version = api_version.strip().lower()
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    base = self._base(wid, api_version)
    if id:
      env = self._data(self.client.get(f"{base}/{quote_plus(id)}").json())
      if not (env.get("id") or env.get("Id")):
        raise DuploNotFound(id, self.kind)
      return env

    if not name:
      raise DuploError("Either an environment name or --id is required")

    response = self.client.get(
        f"{base}?filters[name]={quote_plus(name)}").json()
    target = name.lower()
    match = next((e for e in self._items(response)
                  if (e.get("name") or e.get("Name") or "").lower() == target),
                 None)
    if not match:
      raise DuploNotFound(name, self.kind)
    return match

  @Command()
  def create(self,
             body: args.BODY,
             workspace: args.WORKSPACE = None,
             workspace_id: args.WORKSPACEID = None,
             api_version: args.APIVERSION = "v1") -> dict:
    """Create an AI HelpDesk environment in a workspace.

    An environment is a logical grouping with no provisioning lifecycle,
    so it is usable as soon as it is created.

    Usage: CLI Usage
      ```sh
      duploctl environment create -f environment.yaml --workspace <workspace>
      ```

    Args:
      body: The environment definition (at minimum a ``name``).
      workspace: The workspace name the environment belongs to.
      workspace_id: The workspace id the environment belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The created environment object.

    Raises:
      DuploError: If no body is provided.
    """
    api_version = api_version.strip().lower()
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    response = self.client.post(
        self._base(wid, api_version), body).json()
    return self._data(response)

  @Command()
  def update(self,
             body: args.BODY = None,
             name: args.NAME = None,
             id: args.ID = None,
             workspace: args.WORKSPACE = None,
             workspace_id: args.WORKSPACEID = None,
             api_version: args.APIVERSION = "v1") -> dict:
    """Update an AI HelpDesk environment.

    The target is resolved by ``--id``, ``name``, or the body's ``name``
    field, in that order.

    Usage: CLI Usage
      ```sh
      duploctl environment update <name> -f environment.yaml --workspace <workspace>
      duploctl environment update -f environment.yaml --workspace <workspace>
      ```

    Args:
      body: The environment definition to apply.
      name: The environment name. Defaults to the body's ``name``.
      id: The environment id. Skips the name lookup when provided.
      workspace: The workspace name the environment belongs to.
      workspace_id: The workspace id the environment belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The updated environment object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the environment cannot be found.
    """
    api_version = api_version.strip().lower()
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    env = self.find(
        name=name or body.get("name"), id=id, workspace_id=wid,
        api_version=api_version)
    eid = env.get("id") or env.get("Id")
    # The backend rejects the PUT as a self name-collision unless the body
    # carries its own id, matching the workspace/agent update contract.
    body = {**body, "id": eid}
    response = self.client.put(
        f"{self._base(wid, api_version)}/{quote_plus(eid)}", body).json()
    return self._data(response)

  @Command()
  def apply(self,
            body: args.BODY,
            workspace: args.WORKSPACE = None,
            workspace_id: args.WORKSPACEID = None,
            api_version: args.APIVERSION = "v1") -> dict:
    """Create or update an AI HelpDesk environment.

    Looks the environment up by the body's ``name``: updates it when it
    exists, creates it otherwise.

    Usage: CLI Usage
      ```sh
      duploctl environment apply -f environment.yaml --workspace <workspace>
      ```

    Args:
      body: The environment definition to apply.
      workspace: The workspace name the environment belongs to.
      workspace_id: The workspace id the environment belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The created or updated environment object.

    Raises:
      DuploError: If no body is provided.
    """
    api_version = api_version.strip().lower()
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    try:
      self.find(name=body.get("name"), workspace_id=wid,
                api_version=api_version)
    except DuploNotFound:
      return self.create(
          body=body, workspace_id=wid, api_version=api_version)
    return self.update(body=body, workspace_id=wid, api_version=api_version)

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None,
             workspace: args.WORKSPACE = None,
             workspace_id: args.WORKSPACEID = None,
             api_version: args.APIVERSION = "v1") -> dict:
    """Delete an AI HelpDesk environment by name or id.

    Usage: CLI Usage
      ```sh
      duploctl environment delete <name> --workspace <workspace>
      duploctl environment delete --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The environment name as shown in the portal.
      id: The environment id. Skips the name lookup when provided.
      workspace: The workspace name the environment belongs to.
      workspace_id: The workspace id the environment belongs to.
      api_version: Helpdesk API version.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If no environment matches the name or id.
    """
    api_version = api_version.strip().lower()
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    env = self.find(
        name=name, id=id, workspace_id=wid, api_version=api_version)
    eid = env.get("id") or env.get("Id")
    self.client.delete(
        f"{self._base(wid, api_version)}/{quote_plus(eid)}")
    return {"message": f"environment '{name or id}' deleted"}
