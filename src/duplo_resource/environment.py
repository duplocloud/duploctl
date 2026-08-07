from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.commander import Command, Resource
from duplo_resource.helpdesk import HelpdeskResource
from duplo_resource.helpdesk_client import unwrap_data
import duplocloud.args as args


@Resource("environment", scope="workspace", client="helpdesk")
class DuploEnvironment(HelpdeskResource):
  """Manage AI HelpDesk (HDV2) environments in DuploCloud.

  An environment groups resource groups and their workloads inside a
  workspace. Environments are resolved by name to their id so the same
  name-or-id lookup is shared across the CLI. The workspace comes from
  the global ``-W``/``--workspace-id`` flags (or ``DUPLO_WORKSPACE``/
  ``DUPLO_WORKSPACE_ID``) via the workspace scope.
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)

  def _base(self) -> str:
    """Build the workspace-scoped environments endpoint."""
    return (f"user/data/workspaces/{self.workspace_id}/environments")

  @Command("ls")
  def list(self) -> list:
    """Retrieve the environments in an AI HelpDesk workspace.

    Usage: CLI Usage
      ```sh
      duploctl environment list -W <workspace>
      duploctl environment list --workspace-id <workspace id>
      ```

    Returns:
      list: The environments in the workspace.
    """
    return self.client.get_items(self._base())

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None) -> dict:
    """Find an AI HelpDesk environment by name or id within a workspace.

    With ``--id`` the environment is fetched directly. Otherwise it is
    matched by name (case-insensitive) from the workspace's environments.

    Usage: CLI Usage
      ```sh
      duploctl environment find <name> -W <workspace>
      duploctl environment find --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The environment name as shown in the portal.
      id: The environment id. Skips the name lookup when provided.

    Returns:
      resource: The matching environment object.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no environment matches the name or id.
    """
    return self._find_in_workspace(name, id)

  @Command()
  def create(self, body: args.BODY) -> dict:
    """Create an AI HelpDesk environment in a workspace.

    An environment is a logical grouping with no provisioning lifecycle,
    so it is usable as soon as it is created.

    Usage: CLI Usage
      ```sh
      duploctl environment create -f environment.yaml -W <workspace>
      ```

    Args:
      body: The environment definition (at minimum a ``name``).

    Returns:
      resource: The created environment object.

    Raises:
      DuploError: If no body is provided.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    response = self.client.post(self._base(), body).json()
    return unwrap_data(response)

  @Command()
  def update(self,
             body: args.BODY = None,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Update an AI HelpDesk environment.

    The target is resolved by ``--id``, ``name``, or the body's ``name``
    field, in that order.

    Usage: CLI Usage
      ```sh
      duploctl environment update <name> -f environment.yaml -W <workspace>
      duploctl environment update -f environment.yaml -W <workspace>
      ```

    Args:
      body: The environment definition to apply.
      name: The environment name. Defaults to the body's ``name``.
      id: The environment id. Skips the name lookup when provided.

    Returns:
      resource: The updated environment object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the environment cannot be found.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    env = self.find(name=name or body.get("name"), id=id)
    eid = self._id_of(env)
    response = self.client.put(
        f"{self._base()}/{quote_plus(eid)}", body).json()
    return unwrap_data(response)

  @Command()
  def apply(self, body: args.BODY) -> dict:
    """Create or update an AI HelpDesk environment.

    Looks the environment up by the body's ``name``: updates it when it
    exists, creates it otherwise.

    Usage: CLI Usage
      ```sh
      duploctl environment apply -f environment.yaml -W <workspace>
      ```

    Args:
      body: The environment definition to apply.

    Returns:
      resource: The created or updated environment object.

    Raises:
      DuploError: If no body is provided or it has no ``name``.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    if not body.get("name"):
      raise DuploError("The body must include a 'name'")
    try:
      self.find(name=body.get("name"))
    except DuploNotFound:
      return self.create(body=body)
    return self.update(body=body)

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Delete an AI HelpDesk environment by name or id.

    Usage: CLI Usage
      ```sh
      duploctl environment delete <name> -W <workspace>
      duploctl environment delete --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The environment name as shown in the portal.
      id: The environment id. Skips the name lookup when provided.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If no environment matches the name or id.
    """
    env = self.find(name=name, id=id)
    eid = self._id_of(env)
    self.client.delete(f"{self._base()}/{quote_plus(eid)}")
    return {"message": f"environment '{name or id}' deleted"}
