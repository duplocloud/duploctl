from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.commander import Command, Resource
from duplo_resource.helpdesk import HelpdeskResource
from duplo_resource.helpdesk_client import unwrap_data, unwrap_items
import duplocloud.args as args


@Resource("appservice", scope="workspace", client="helpdesk")
class DuploAppService(HelpdeskResource):
  """Manage AI HelpDesk (HDV2) Kubernetes AppServices in DuploCloud.

  An AppService is the HelpDesk V2 representation of a Kubernetes
  Deployment/StatefulSet workload (the EKS equivalent of a Core Platform
  service). AppServices live inside a workspace, under an
  environment/resource-group; ``find``/``list``/``update_image`` operate
  at the workspace scope, while ``create``/``update``/``delete`` use the
  nested environment/resource-group scope. Environment and
  resource-group resolution are delegated to their respective resources
  via the shared :class:`HelpdeskResource` helpers; the workspace comes
  from the global ``-W``/``--workspace-id`` flags.
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)

  def _base(self) -> str:
    """Build the workspace-scoped appservices endpoint."""
    return (f"user/data/workspaces/{self.workspace_id}/"
            f"environment/appservices")

  def _nested_base(self,
                   environment_id: str,
                   resource_group_id: str) -> str:
    """Build the env/resource-group-scoped appservices endpoint."""
    return (f"user/data/workspaces/{self.workspace_id}/environments/"
            f"{quote_plus(environment_id)}/resource-groups/"
            f"{quote_plus(resource_group_id)}/appservices")

  @Command("ls")
  def list(self) -> list:
    """Retrieve the AppServices in an AI HelpDesk workspace.

    Usage: CLI Usage
      ```sh
      duploctl appservice list -W <workspace>
      duploctl appservice list --workspace-id <workspace id>
      ```

    Returns:
      list: The appservices in the workspace.
    """
    response = self.client.get(self._base()).json()
    return unwrap_items(response)

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None) -> dict:
    """Find an AI HelpDesk AppService by name or id within a workspace.

    Usage: CLI Usage
      ```sh
      duploctl appservice find <name> -W <workspace>
      duploctl appservice find --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The appservice name as shown in the portal.
      id: The appservice id. Skips the name lookup when provided.

    Returns:
      resource: The matching appservice object.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no appservice matches the name or id.
    """
    return self._find_in_workspace(name, id)

  @Command()
  def create(self,
             body: args.BODY,
             environment: args.ENVIRONMENT = None,
             environment_id: args.ENVIRONMENTID = None,
             resource_group: args.RESOURCEGROUP = None,
             resource_group_id: args.RESOURCEGROUPID = None) -> dict:
    """Create an AI HelpDesk AppService under an environment/resource group.

    The appservice is created on the nested environment/resource-group
    route, which the backend uses to stamp the placement onto the spec.
    The environment and resource group are resolved by name or id via
    their respective resources.

    Usage: CLI Usage
      ```sh
      duploctl appservice create -f appservice.yaml -W <workspace> --environment <env> --resource-group <rg>
      ```

    Args:
      body: The appservice definition.
      environment: The environment name to create the appservice in.
      environment_id: The environment id. Skips the environment lookup.
      resource_group: The resource group name to create the appservice in.
      resource_group_id: The resource group id. Skips the lookup.

    Returns:
      resource: The created appservice object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the environment or resource group is not found.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    eid, rgid = self._resolve_env_rg(
        environment, environment_id, resource_group, resource_group_id)
    response = self.client.post(self._nested_base(eid, rgid), body).json()
    return unwrap_data(response)

  @Command()
  def update(self,
             body: args.BODY = None,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Update an AI HelpDesk AppService.

    The target is resolved by ``--id``, ``name``, or the body's ``name``
    field, in that order. The environment/resource-group ids are read off
    the existing record to build the nested update route.

    Usage: CLI Usage
      ```sh
      duploctl appservice update <name> -f appservice.yaml -W <workspace>
      duploctl appservice update -f appservice.yaml -W <workspace>
      ```

    Args:
      body: The appservice definition to apply.
      name: The appservice name. Defaults to the body's ``name``.
      id: The appservice id. Skips the name lookup when provided.

    Returns:
      resource: The updated appservice object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the appservice cannot be found.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    appsvc = self._find_in_workspace(name or body.get("name"), id)
    aid = self._id_of(appsvc)
    eid, rgid = self._record_env_rg(appsvc)
    # The backend rejects the PUT as a self name-collision unless the body
    # carries its own id, matching the workspace/agent update contract.
    body = {**body, "id": aid}
    response = self.client.put(
        f"{self._nested_base(eid, rgid)}/{quote_plus(aid)}", body).json()
    return unwrap_data(response)

  @Command()
  def apply(self,
            body: args.BODY,
            environment: args.ENVIRONMENT = None,
            environment_id: args.ENVIRONMENTID = None,
            resource_group: args.RESOURCEGROUP = None,
            resource_group_id: args.RESOURCEGROUPID = None) -> dict:
    """Create or update an AI HelpDesk AppService.

    Looks the appservice up by the body's ``name``: updates it when it
    exists, creates it otherwise. The environment/resource-group
    selectors are only used on the create path.

    Usage: CLI Usage
      ```sh
      duploctl appservice apply -f appservice.yaml -W <workspace> --environment <env> --resource-group <rg>
      ```

    Args:
      body: The appservice definition to apply.
      environment: The environment name (used when creating).
      environment_id: The environment id (used when creating).
      resource_group: The resource group name (used when creating).
      resource_group_id: The resource group id (used when creating).

    Returns:
      resource: The created or updated appservice object.

    Raises:
      DuploError: If no body is provided or it has no ``name``.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    if not body.get("name"):
      raise DuploError("The body must include a 'name'")
    try:
      self._find_in_workspace(body.get("name"), None)
    except DuploNotFound:
      return self.create(
          body=body, environment=environment, environment_id=environment_id,
          resource_group=resource_group, resource_group_id=resource_group_id)
    return self.update(body=body)

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Deprovision an AI HelpDesk AppService.

    Initiates deprovisioning on the nested environment/resource-group
    route (the HelpDesk V2 teardown for a workload); the ids are read off
    the existing record.

    Usage: CLI Usage
      ```sh
      duploctl appservice delete <name> -W <workspace>
      duploctl appservice delete --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The appservice name as shown in the portal.
      id: The appservice id. Skips the name lookup when provided.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If the appservice cannot be found.
    """
    appsvc = self._find_in_workspace(name, id)
    aid = self._id_of(appsvc)
    eid, rgid = self._record_env_rg(appsvc)
    self.client.post(
        f"{self._nested_base(eid, rgid)}/{quote_plus(aid)}/deprovision")
    return {"message": f"appservice '{name or id}' deprovisioning initiated"}

  @Command()
  def update_image(self,
                   name: args.NAME,
                   image: args.IMAGE) -> dict:
    """Update the container image of an AI HelpDesk AppService.

    Updates the image on the first container of the appservice's
    Deployment or StatefulSet. The appservice is resolved to its id
    within the workspace, then the HelpDesk ``update-image`` endpoint is
    called.

    Usage: CLI Usage
      ```sh
      duploctl appservice update_image <name> <image> -W <workspace>
      ```

    Args:
      name: The name of the appservice to update.
      image: The new container image (e.g. ``nginx:1.27``).

    Returns:
      resource: The updated appservice object.

    Raises:
      DuploError: If no image is given or the workspace cannot be resolved.
      DuploNotFound: If the appservice cannot be found.
    """
    if not image or not image.strip():
      raise DuploError("An image is required")
    appsvc = self._find_in_workspace(name, None)
    aid = self._id_of(appsvc)
    response = self.client.post(
        f"{self._base()}/{quote_plus(aid)}/update-image",
        {"image": image}).json()
    return unwrap_data(response)
