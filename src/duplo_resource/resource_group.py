from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.commander import Command, Resource
from duplo_resource.helpdesk import HelpdeskResource
from duplo_resource.helpdesk_client import unwrap_data
import duplocloud.args as args


@Resource("resource_group", scope="workspace", client="helpdesk")
class DuploResourceGroup(HelpdeskResource):
  """Manage AI HelpDesk (HDV2) resource groups in DuploCloud.

  A resource group lives inside an environment within a workspace and
  parents the workloads (appservices, lambdas). Resource groups are
  resolved by name to their id; environment resolution is delegated to
  the ``environment`` resource via the shared :class:`HelpdeskResource`
  helpers. The workspace comes from the global ``-W``/``--workspace-id``
  flags (or ``DUPLO_WORKSPACE``/``DUPLO_WORKSPACE_ID``).
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)

  def _base(self) -> str:
    """Build the workspace-scoped resource-groups endpoint."""
    return (f"user/data/workspaces/{self.workspace_id}/"
            f"environment/resource-groups")

  def _nested_base(self, environment_id: str) -> str:
    """Build the environment-scoped resource-groups create endpoint."""
    return (f"user/data/workspaces/{self.workspace_id}/environments/"
            f"{quote_plus(environment_id)}/resource-groups")

  @Command("ls")
  def list(self,
           environment: args.ENVIRONMENT = None,
           environment_id: args.ENVIRONMENTID = None) -> list:
    """Retrieve the resource groups in an AI HelpDesk workspace.

    When an environment is given the results are narrowed to that
    environment (resource-group names are only unique within one).

    Usage: CLI Usage
      ```sh
      duploctl resource_group list -W <workspace>
      duploctl resource_group list -W <workspace> --environment <env>
      ```

    Args:
      environment: Narrow the results to this environment name.
      environment_id: Narrow the results to this environment id.

    Returns:
      list: The resource groups in the workspace (optionally scoped to an
        environment).
    """
    items = self.client.get_items(self._base())
    if environment or environment_id:
      eid = self._resolve_environment_id(environment, environment_id)
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
           environment: args.ENVIRONMENT = None,
           environment_id: args.ENVIRONMENTID = None) -> dict:
    """Find an AI HelpDesk resource group by name or id.

    With ``--id`` the resource group is fetched directly. Otherwise it is
    matched by name (case-insensitive); pass an environment to
    disambiguate when the same name exists across environments.

    Usage: CLI Usage
      ```sh
      duploctl resource_group find <name> -W <workspace>
      duploctl resource_group find --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The resource group name as shown in the portal.
      id: The resource group id. Skips the name lookup when provided.
      environment: Disambiguate the name lookup by environment name.
      environment_id: Disambiguate the name lookup by environment id.

    Returns:
      resource: The matching resource group object.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no resource group matches the name or id.
    """
    if environment or environment_id:
      eid = self._resolve_environment_id(environment, environment_id)
      def where(rg):
        return self._environment_of(rg) == eid
    else:
      where = None
    return self._find_in_workspace(name, id, where=where)

  @Command()
  def create(self,
             body: args.BODY,
             environment: args.ENVIRONMENT = None,
             environment_id: args.ENVIRONMENTID = None) -> dict:
    """Create an AI HelpDesk resource group under an environment.

    The resource group is created on the nested environment route, which
    the backend uses to stamp the environment onto the spec. A resource
    group with ``spec.cloud: K8S_ONLY`` is a purely logical grouping (no
    region/VPC/network required) and is ready immediately; an AWS (or
    other cloud) resource group provisions an IAM/KMS/security-group
    baseline and needs ``spec.region``/``spec.networkId`` in the body.

    Usage: CLI Usage
      ```sh
      duploctl resource_group create -f resource-group.yaml -W <workspace> --environment <env>
      ```

    Args:
      body: The resource group definition (at minimum a ``name``).
      environment: The environment name to create the group in.
      environment_id: The environment id. Skips the environment lookup.

    Returns:
      resource: The created resource group object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the environment cannot be found.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    eid = self._resolve_environment_id(environment, environment_id)
    response = self.client.post(
        self._nested_base(eid), self._strip_scope_ids(body)).json()
    return unwrap_data(response)

  @Command()
  def update(self,
             body: args.BODY = None,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Update an AI HelpDesk resource group.

    The target is resolved by ``--id``, ``name``, or the body's ``name``
    field, in that order. The environment/cluster placement is immutable
    server-side, so only mutable fields take effect.

    Usage: CLI Usage
      ```sh
      duploctl resource_group update <name> -f resource-group.yaml -W <workspace>
      duploctl resource_group update -f resource-group.yaml -W <workspace>
      ```

    Args:
      body: The resource group definition to apply.
      name: The resource group name. Defaults to the body's ``name``.
      id: The resource group id. Skips the name lookup when provided.

    Returns:
      resource: The updated resource group object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the resource group cannot be found.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    rg = self.find(name=name or body.get("name"), id=id)
    rgid = self._id_of(rg)
    body = dict(body)
    # The spec's placement fields are immutable server-side. Omitted ones are
    # restored from the stored record by the backend, except cloud: it is a
    # non-nullable enum that deserializes to its default when omitted, so a
    # body with a spec but no cloud reads as an attempt to change it and is
    # rejected for any non-default cloud. Carry the immutable fields forward
    # from the existing record so a partial spec always round-trips.
    existing_spec = rg.get("spec") or rg.get("Spec") or {}
    spec = dict(body.get("spec") or {})
    for field in ("environmentId", "clusterId", "awsResourceName", "cloud"):
      pascal = field[0].upper() + field[1:]
      value = existing_spec.get(field) or existing_spec.get(pascal)
      if value and not (spec.get(field) or spec.get(pascal)):
        spec[field] = value
    if spec:
      body["spec"] = spec
    response = self.client.put(
        f"{self._base()}/{quote_plus(rgid)}", body).json()
    return unwrap_data(response)

  @Command()
  def apply(self,
            body: args.BODY,
            environment: args.ENVIRONMENT = None,
            environment_id: args.ENVIRONMENTID = None) -> dict:
    """Create or update an AI HelpDesk resource group.

    Looks the resource group up by the body's ``name``: updates it when
    it exists, creates it otherwise. The environment selector is only
    used on the create path.

    Usage: CLI Usage
      ```sh
      duploctl resource_group apply -f resource-group.yaml -W <workspace> --environment <env>
      ```

    Args:
      body: The resource group definition to apply.
      environment: The environment name (used when creating).
      environment_id: The environment id (used when creating).

    Returns:
      resource: The created or updated resource group object.

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
      return self.create(
          body=body, environment=environment, environment_id=environment_id)
    return self.update(body=body)

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Delete an AI HelpDesk resource group by name or id.

    Removes the resource group record directly. The backend only allows
    this for groups that are already deprovisioned (or were imported), so
    run ``deprovision`` first for a live group — that is the orchestrated
    cascade teardown that also removes child resources.

    Usage: CLI Usage
      ```sh
      duploctl resource_group delete <name> -W <workspace>
      duploctl resource_group delete --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The resource group name as shown in the portal.
      id: The resource group id. Skips the name lookup when provided.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If no resource group matches the name or id.
    """
    rg = self.find(name=name, id=id)
    rgid = self._id_of(rg)
    self.client.delete(f"{self._base()}/{quote_plus(rgid)}")
    return {"message": f"resource group '{name or id}' deleted"}

  @Command()
  def deprovision(self,
                  name: args.NAME = None,
                  id: args.ID = None) -> dict:
    """Cascade-deprovision an AI HelpDesk resource group.

    Initiates the orchestrated teardown of the resource group and all of
    its child resources. The backend requires every direct child to be
    confirmed, so the deprovision preview is fetched first and all of its
    ids are submitted.

    Usage: CLI Usage
      ```sh
      duploctl resource_group deprovision <name> -W <workspace>
      duploctl resource_group deprovision --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The resource group name as shown in the portal.
      id: The resource group id. Skips the name lookup when provided.

    Returns:
      message: A success message noting how many children were included.

    Raises:
      DuploNotFound: If no resource group matches the name or id.
    """
    rg = self.find(name=name, id=id)
    rgid = self._id_of(rg)
    base = self._base()
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
