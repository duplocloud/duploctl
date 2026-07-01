from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("resource_group", scope="tenant")
class DuploResourceGroup(DuploResource):
  """Manage AI HelpDesk (HDV2) resource groups in DuploCloud.

  A resource group lives inside an environment within a workspace and
  parents the workloads (appservices, lambdas). Resource groups are
  resolved by name to their id; workspace and environment resolution are
  delegated to the ``workspace`` and ``environment`` resources.
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo, api_version="v1")
    self.__workspace_svc = self.duplo.load("workspace")
    self.__environment_svc = self.duplo.load("environment")

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

  def _resolve_environment_id(self,
                              workspace_id: str,
                              environment: str,
                              environment_id: str,
                              api_version: str) -> str:
    """Resolve an environment name/id to its id, scoped to the workspace."""
    return self.__environment_svc.find(
        name=environment, id=environment_id, workspace_id=workspace_id,
        api_version=api_version)["id"]

  def _base(self, workspace_id: str, api_version: str) -> str:
    """Build the workspace-scoped resource-groups endpoint."""
    return (f"{api_version}/aiservicedesk/user/data/workspaces/"
            f"{workspace_id}/environment/resource-groups")

  def _nested_base(self,
                   workspace_id: str,
                   environment_id: str,
                   api_version: str) -> str:
    """Build the environment-scoped resource-groups create endpoint."""
    return (f"{api_version}/aiservicedesk/user/data/workspaces/"
            f"{workspace_id}/environments/{quote_plus(environment_id)}/"
            f"resource-groups")

  @Command("ls")
  def list(self,
           workspace: args.WORKSPACE = None,
           workspace_id: args.WORKSPACEID = None,
           environment: args.ENVIRONMENT = None,
           environment_id: args.ENVIRONMENTID = None,
           api_version: args.APIVERSION = "v1") -> list:
    """Retrieve the resource groups in an AI HelpDesk workspace.

    When an environment is given the results are narrowed to that
    environment (resource-group names are only unique within one).

    Usage: CLI Usage
      ```sh
      duploctl resource_group list --workspace <workspace>
      duploctl resource_group list --workspace <workspace> --environment <env>
      ```

    Args:
      workspace: The workspace name the resource groups belong to.
      workspace_id: The workspace id the resource groups belong to.
      environment: Narrow the results to this environment name.
      environment_id: Narrow the results to this environment id.
      api_version: Helpdesk API version.

    Returns:
      list: The resource groups in the workspace (optionally scoped to an
        environment).
    """
    api_version = api_version.strip().lower()
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    items = self._items(self.client.get(self._base(wid, api_version)).json())
    if environment or environment_id:
      eid = self._resolve_environment_id(
          wid, environment, environment_id, api_version)
      items = [rg for rg in items if self._environment_of(rg) == eid]
    return items

  def _environment_of(self, resource_group: dict) -> str:
    """Read the environment id off a resource-group record's spec."""
    spec = resource_group.get("spec") or resource_group.get("Spec") or {}
    return spec.get("environmentId") or spec.get("EnvironmentId")

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None,
           workspace: args.WORKSPACE = None,
           workspace_id: args.WORKSPACEID = None,
           environment: args.ENVIRONMENT = None,
           environment_id: args.ENVIRONMENTID = None,
           api_version: args.APIVERSION = "v1") -> dict:
    """Find an AI HelpDesk resource group by name or id.

    With ``--id`` the resource group is fetched directly. Otherwise it is
    matched by name (case-insensitive); pass an environment to
    disambiguate when the same name exists across environments.

    Usage: CLI Usage
      ```sh
      duploctl resource_group find <name> --workspace <workspace>
      duploctl resource_group find --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The resource group name as shown in the portal.
      id: The resource group id. Skips the name lookup when provided.
      workspace: The workspace name the resource group belongs to.
      workspace_id: The workspace id the resource group belongs to.
      environment: Disambiguate the name lookup by environment name.
      environment_id: Disambiguate the name lookup by environment id.
      api_version: Helpdesk API version.

    Returns:
      resource: The matching resource group object.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no resource group matches the name or id.
    """
    api_version = api_version.strip().lower()
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    base = self._base(wid, api_version)
    if id:
      rg = self._data(self.client.get(f"{base}/{quote_plus(id)}").json())
      if not (rg.get("id") or rg.get("Id")):
        raise DuploNotFound(id, self.kind)
      return rg

    if not name:
      raise DuploError("Either a resource group name or --id is required")

    eid = None
    if environment or environment_id:
      eid = self._resolve_environment_id(
          wid, environment, environment_id, api_version)

    response = self.client.get(
        f"{base}?filters[name]={quote_plus(name)}").json()
    target = name.lower()
    match = next(
        (rg for rg in self._items(response)
         if (rg.get("name") or rg.get("Name") or "").lower() == target
         and (eid is None or self._environment_of(rg) == eid)),
        None)
    if not match:
      raise DuploNotFound(name, self.kind)
    return match

  @Command()
  def create(self,
             body: args.BODY,
             environment: args.ENVIRONMENT = None,
             environment_id: args.ENVIRONMENTID = None,
             workspace: args.WORKSPACE = None,
             workspace_id: args.WORKSPACEID = None,
             api_version: args.APIVERSION = "v1") -> dict:
    """Create an AI HelpDesk resource group under an environment.

    The resource group is created on the nested environment route, which
    the backend uses to stamp the environment onto the spec. A resource
    group with ``spec.cloud: K8S_ONLY`` is a purely logical grouping (no
    region/VPC/network required) and is ready immediately; an AWS (or
    other cloud) resource group provisions an IAM/KMS/security-group
    baseline and needs ``spec.region``/``spec.networkId`` in the body.

    Usage: CLI Usage
      ```sh
      duploctl resource_group create -f resource-group.yaml --workspace <workspace> --environment <env>
      ```

    Args:
      body: The resource group definition (at minimum a ``name``).
      environment: The environment name to create the group in.
      environment_id: The environment id. Skips the environment lookup.
      workspace: The workspace name the resource group belongs to.
      workspace_id: The workspace id the resource group belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The created resource group object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the environment cannot be found.
    """
    api_version = api_version.strip().lower()
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    eid = self._resolve_environment_id(
        wid, environment, environment_id, api_version)
    response = self.client.post(
        self._nested_base(wid, eid, api_version), body).json()
    return self._data(response)

  @Command()
  def update(self,
             body: args.BODY = None,
             name: args.NAME = None,
             id: args.ID = None,
             workspace: args.WORKSPACE = None,
             workspace_id: args.WORKSPACEID = None,
             api_version: args.APIVERSION = "v1") -> dict:
    """Update an AI HelpDesk resource group.

    The target is resolved by ``--id``, ``name``, or the body's ``name``
    field, in that order. The environment/cluster placement is immutable
    server-side, so only mutable fields take effect.

    Usage: CLI Usage
      ```sh
      duploctl resource_group update <name> -f resource-group.yaml --workspace <workspace>
      duploctl resource_group update -f resource-group.yaml --workspace <workspace>
      ```

    Args:
      body: The resource group definition to apply.
      name: The resource group name. Defaults to the body's ``name``.
      id: The resource group id. Skips the name lookup when provided.
      workspace: The workspace name the resource group belongs to.
      workspace_id: The workspace id the resource group belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The updated resource group object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the resource group cannot be found.
    """
    api_version = api_version.strip().lower()
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    rg = self.find(
        name=name or body.get("name"), id=id, workspace_id=wid,
        api_version=api_version)
    rgid = rg.get("id") or rg.get("Id")
    # The backend rejects the PUT as a self name-collision unless the body
    # carries its own id, matching the workspace/agent update contract.
    body = {**body, "id": rgid}
    # The workspace-scoped update route (unlike the nested create) carries no
    # environment in the URL, so the backend reads a missing spec placement as
    # an attempt to null out the immutable environmentId/clusterId and rejects
    # it. Carry those forward from the existing record when the body omits them.
    existing_spec = rg.get("spec") or rg.get("Spec") or {}
    spec = dict(body.get("spec") or {})
    for field in ("environmentId", "clusterId", "awsResourceName"):
      if not spec.get(field) and existing_spec.get(field):
        spec[field] = existing_spec[field]
    if spec:
      body["spec"] = spec
    response = self.client.put(
        f"{self._base(wid, api_version)}/{quote_plus(rgid)}", body).json()
    return self._data(response)

  @Command()
  def apply(self,
            body: args.BODY,
            environment: args.ENVIRONMENT = None,
            environment_id: args.ENVIRONMENTID = None,
            workspace: args.WORKSPACE = None,
            workspace_id: args.WORKSPACEID = None,
            api_version: args.APIVERSION = "v1") -> dict:
    """Create or update an AI HelpDesk resource group.

    Looks the resource group up by the body's ``name``: updates it when
    it exists, creates it otherwise. The environment selector is only
    used on the create path.

    Usage: CLI Usage
      ```sh
      duploctl resource_group apply -f resource-group.yaml --workspace <workspace> --environment <env>
      ```

    Args:
      body: The resource group definition to apply.
      environment: The environment name (used when creating).
      environment_id: The environment id (used when creating).
      workspace: The workspace name the resource group belongs to.
      workspace_id: The workspace id the resource group belongs to.
      api_version: Helpdesk API version.

    Returns:
      resource: The created or updated resource group object.

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
          body=body, environment=environment, environment_id=environment_id,
          workspace_id=wid, api_version=api_version)
    return self.update(body=body, workspace_id=wid, api_version=api_version)

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None,
             workspace: args.WORKSPACE = None,
             workspace_id: args.WORKSPACEID = None,
             api_version: args.APIVERSION = "v1") -> dict:
    """Delete an AI HelpDesk resource group by name or id.

    Removes the resource group record directly. Use ``deprovision`` for
    the orchestrated cascade teardown that also removes child resources.

    Usage: CLI Usage
      ```sh
      duploctl resource_group delete <name> --workspace <workspace>
      duploctl resource_group delete --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The resource group name as shown in the portal.
      id: The resource group id. Skips the name lookup when provided.
      workspace: The workspace name the resource group belongs to.
      workspace_id: The workspace id the resource group belongs to.
      api_version: Helpdesk API version.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If no resource group matches the name or id.
    """
    api_version = api_version.strip().lower()
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    rg = self.find(
        name=name, id=id, workspace_id=wid, api_version=api_version)
    rgid = rg.get("id") or rg.get("Id")
    self.client.delete(
        f"{self._base(wid, api_version)}/{quote_plus(rgid)}")
    return {"message": f"resource group '{name or id}' deleted"}

  @Command()
  def deprovision(self,
                  name: args.NAME = None,
                  id: args.ID = None,
                  workspace: args.WORKSPACE = None,
                  workspace_id: args.WORKSPACEID = None,
                  api_version: args.APIVERSION = "v1") -> dict:
    """Cascade-deprovision an AI HelpDesk resource group.

    Initiates the orchestrated teardown of the resource group and all of
    its child resources. The backend requires every direct child to be
    confirmed, so the deprovision preview is fetched first and all of its
    ids are submitted.

    Usage: CLI Usage
      ```sh
      duploctl resource_group deprovision <name> --workspace <workspace>
      duploctl resource_group deprovision --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The resource group name as shown in the portal.
      id: The resource group id. Skips the name lookup when provided.
      workspace: The workspace name the resource group belongs to.
      workspace_id: The workspace id the resource group belongs to.
      api_version: Helpdesk API version.

    Returns:
      message: A success message noting how many children were included.

    Raises:
      DuploNotFound: If no resource group matches the name or id.
    """
    api_version = api_version.strip().lower()
    wid = self._resolve_workspace_id(workspace, workspace_id, api_version)
    rg = self.find(
        name=name, id=id, workspace_id=wid, api_version=api_version)
    rgid = rg.get("id") or rg.get("Id")
    base = self._base(wid, api_version)
    # The backend rejects a partial selection, so confirm every direct
    # child returned by the preview. The preview envelope wraps a bare
    # list under ``data`` (not the ``data.items`` page shape).
    preview = self.client.get(
        f"{base}/{quote_plus(rgid)}/deprovision-preview").json()
    items = preview.get("data") if isinstance(preview, dict) else preview
    items = items or []
    child_ids = [i.get("id") or i.get("Id") for i in items
                 if (i.get("id") or i.get("Id"))]
    self.client.post(
        f"{base}/{quote_plus(rgid)}/deprovision",
        {"selectedResourceIds": child_ids})
    return {"message": f"resource group '{name or id}' deprovisioning "
                       f"initiated with {len(child_ids)} child resource(s)"}
