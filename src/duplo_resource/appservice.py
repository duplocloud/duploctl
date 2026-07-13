from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.commander import Command, Resource
from duplo_resource.helpdesk import HelpdeskResource
import duplocloud.args as args


@Resource("appservice", scope="tenant")
class DuploAppService(HelpdeskResource):
  """Manage AI HelpDesk (HDV2) Kubernetes AppServices in DuploCloud.

  An AppService is the HelpDesk V2 representation of a Kubernetes
  Deployment/StatefulSet workload (the EKS equivalent of a Core Platform
  service). AppServices live inside a workspace, under an
  environment/resource-group; ``find``/``list``/``update_image`` operate
  at the workspace scope, while ``create``/``update``/``delete`` use the
  nested environment/resource-group scope. Workspace, environment, and
  resource-group resolution are delegated to their respective resources
  via the shared :class:`HelpdeskResource` helpers.
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)

  def _base(self, workspace_id: str, api_version: str) -> str:
    """Build the workspace-scoped appservices endpoint."""
    return (f"{api_version}/aiservicedesk/user/data/workspaces/"
            f"{workspace_id}/environment/appservices")

  def _nested_base(self,
                   workspace_id: str,
                   environment_id: str,
                   resource_group_id: str,
                   api_version: str) -> str:
    """Build the env/resource-group-scoped appservices endpoint."""
    return (f"{api_version}/aiservicedesk/user/data/workspaces/"
            f"{workspace_id}/environments/{quote_plus(environment_id)}/"
            f"resource-groups/{quote_plus(resource_group_id)}/appservices")

  @Command("ls")
  def list(self,
           workspace: args.WORKSPACE = None,
           workspace_id: args.WORKSPACEID = None,
           api_version: args.APIVERSION = "v1") -> list:
    """Retrieve the AppServices in an AI HelpDesk workspace.

    Usage: CLI Usage
      ```sh
      duploctl appservice list --workspace <workspace>
      duploctl appservice list --workspace-id <workspace id>
      ```

    Args:
      workspace: The workspace name the appservices belong to.
      workspace_id: The workspace id the appservices belong to.
      api_version: Helpdesk API version.

    Returns:
      list: The appservices in the workspace.
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
    """Find an AI HelpDesk AppService by name or id within a workspace.

    Usage: CLI Usage
      ```sh
      duploctl appservice find <name> --workspace <workspace>
      duploctl appservice find --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The appservice name as shown in the portal.
      id: The appservice id. Skips the name lookup when provided.
      workspace: The workspace name the appservice belongs to.
      workspace_id: The workspace id the appservice belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The matching appservice object.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no appservice matches the name or id.
    """
    api_version = api_version.strip().lower()
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    return self._find_in_workspace(wid, name, id, api_version)

  @Command()
  def create(self,
             body: args.BODY,
             environment: args.ENVIRONMENT = None,
             environment_id: args.ENVIRONMENTID = None,
             resource_group: args.RESOURCEGROUP = None,
             resource_group_id: args.RESOURCEGROUPID = None,
             workspace: args.WORKSPACE = None,
             workspace_id: args.WORKSPACEID = None,
             api_version: args.APIVERSION = "v1") -> dict:
    """Create an AI HelpDesk AppService under an environment/resource group.

    The appservice is created on the nested environment/resource-group
    route, which the backend uses to stamp the placement onto the spec.
    The environment and resource group are resolved by name or id via
    their respective resources.

    Usage: CLI Usage
      ```sh
      duploctl appservice create -f appservice.yaml --workspace <workspace> --environment <env> --resource-group <rg>
      ```

    Args:
      body: The appservice definition.
      environment: The environment name to create the appservice in.
      environment_id: The environment id. Skips the environment lookup.
      resource_group: The resource group name to create the appservice in.
      resource_group_id: The resource group id. Skips the lookup.
      workspace: The workspace name the appservice belongs to.
      workspace_id: The workspace id the appservice belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The created appservice object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the environment or resource group is not found.
    """
    api_version = api_version.strip().lower()
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    eid, rgid = self._resolve_env_rg(
        wid, environment, environment_id,
        resource_group, resource_group_id, api_version)
    response = self.client.post(
        self._nested_base(wid, eid, rgid, api_version), body).json()
    return self._data(response)

  @Command()
  def update(self,
             body: args.BODY = None,
             name: args.NAME = None,
             id: args.ID = None,
             workspace: args.WORKSPACE = None,
             workspace_id: args.WORKSPACEID = None,
             api_version: args.APIVERSION = "v1") -> dict:
    """Update an AI HelpDesk AppService.

    The target is resolved by ``--id``, ``name``, or the body's ``name``
    field, in that order. The environment/resource-group ids are read off
    the existing record to build the nested update route.

    Usage: CLI Usage
      ```sh
      duploctl appservice update <name> -f appservice.yaml --workspace <workspace>
      duploctl appservice update -f appservice.yaml --workspace <workspace>
      ```

    Args:
      body: The appservice definition to apply.
      name: The appservice name. Defaults to the body's ``name``.
      id: The appservice id. Skips the name lookup when provided.
      workspace: The workspace name the appservice belongs to.
      workspace_id: The workspace id the appservice belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The updated appservice object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the appservice cannot be found.
    """
    api_version = api_version.strip().lower()
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    appsvc = self._find_in_workspace(
        wid, name or body.get("name"), id, api_version)
    aid = self._id_of(appsvc)
    eid, rgid = self._record_env_rg(appsvc)
    # The backend rejects the PUT as a self name-collision unless the body
    # carries its own id, matching the workspace/agent update contract.
    body = {**body, "id": aid}
    response = self.client.put(
        f"{self._nested_base(wid, eid, rgid, api_version)}/"
        f"{quote_plus(aid)}", body).json()
    return self._data(response)

  @Command()
  def apply(self,
            body: args.BODY,
            environment: args.ENVIRONMENT = None,
            environment_id: args.ENVIRONMENTID = None,
            resource_group: args.RESOURCEGROUP = None,
            resource_group_id: args.RESOURCEGROUPID = None,
            workspace: args.WORKSPACE = None,
            workspace_id: args.WORKSPACEID = None,
            api_version: args.APIVERSION = "v1") -> dict:
    """Create or update an AI HelpDesk AppService.

    Looks the appservice up by the body's ``name``: updates it when it
    exists, creates it otherwise. The environment/resource-group
    selectors are only used on the create path.

    Usage: CLI Usage
      ```sh
      duploctl appservice apply -f appservice.yaml --workspace <workspace> --environment <env> --resource-group <rg>
      ```

    Args:
      body: The appservice definition to apply.
      environment: The environment name (used when creating).
      environment_id: The environment id (used when creating).
      resource_group: The resource group name (used when creating).
      resource_group_id: The resource group id (used when creating).
      workspace: The workspace name the appservice belongs to.
      workspace_id: The workspace id the appservice belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The created or updated appservice object.

    Raises:
      DuploError: If no body is provided or it has no ``name``.
    """
    api_version = api_version.strip().lower()
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    if not body.get("name"):
      raise DuploError("The body must include a 'name'")
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    try:
      self._find_in_workspace(wid, body.get("name"), None, api_version)
    except DuploNotFound:
      return self.create(
          body=body, environment=environment, environment_id=environment_id,
          resource_group=resource_group, resource_group_id=resource_group_id,
          workspace_id=wid, api_version=api_version)
    return self.update(body=body, workspace_id=wid, api_version=api_version)

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None,
             workspace: args.WORKSPACE = None,
             workspace_id: args.WORKSPACEID = None,
             api_version: args.APIVERSION = "v1") -> dict:
    """Deprovision an AI HelpDesk AppService.

    Initiates deprovisioning on the nested environment/resource-group
    route (the HelpDesk V2 teardown for a workload); the ids are read off
    the existing record.

    Usage: CLI Usage
      ```sh
      duploctl appservice delete <name> --workspace <workspace>
      duploctl appservice delete --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The appservice name as shown in the portal.
      id: The appservice id. Skips the name lookup when provided.
      workspace: The workspace name the appservice belongs to.
      workspace_id: The workspace id the appservice belongs to.
      api_version: Helpdesk API version.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If the appservice cannot be found.
    """
    api_version = api_version.strip().lower()
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    appsvc = self._find_in_workspace(wid, name, id, api_version)
    aid = self._id_of(appsvc)
    eid, rgid = self._record_env_rg(appsvc)
    self.client.post(
        f"{self._nested_base(wid, eid, rgid, api_version)}/"
        f"{quote_plus(aid)}/deprovision")
    return {"message": f"appservice '{name or id}' deprovisioning initiated"}

  @Command()
  def update_image(self,
                   name: args.NAME,
                   image: args.IMAGE,
                   workspace: args.WORKSPACE = None,
                   workspace_id: args.WORKSPACEID = None,
                   api_version: args.APIVERSION = "v1") -> dict:
    """Update the container image of an AI HelpDesk AppService.

    Updates the image on the first container of the appservice's
    Deployment or StatefulSet. The appservice is resolved to its id
    within the workspace, then the HelpDesk ``update-image`` endpoint is
    called.

    Usage: CLI Usage
      ```sh
      duploctl appservice update_image <name> <image> --workspace <workspace>
      ```

    Args:
      name: The name of the appservice to update.
      image: The new container image (e.g. ``nginx:1.27``).
      workspace: The workspace name the appservice belongs to.
      workspace_id: The workspace id the appservice belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The updated appservice object.

    Raises:
      DuploError: If no image is given or the workspace cannot be resolved.
      DuploNotFound: If the appservice cannot be found.
    """
    api_version = api_version.strip().lower()
    if not image or not image.strip():
      raise DuploError("An image is required")
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    appsvc = self._find_in_workspace(wid, name, None, api_version)
    aid = self._id_of(appsvc)
    response = self.client.post(
        f"{self._base(wid, api_version)}/{quote_plus(aid)}/update-image",
        {"image": image}).json()
    return self._data(response)
