from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.resource import DuploResource


class HelpdeskResource(DuploResource):
  """Shared plumbing for AI HelpDesk (HDV2) resources.

  Consolidates the response-envelope unwrapping, id-casing tolerance,
  and name→id resolution shared by the HDV2 resources (environment,
  resource group, and the workloads) so the behavior cannot drift
  between them. Sibling resources used for resolution are lazy-loaded
  so instantiating one resource never eagerly instantiates another
  (or, for ``environment``, itself).
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo, api_version="v1")
    self.__workspace_svc = None
    self.__environment_svc = None
    self.__resource_group_svc = None

  @property
  def _workspace_svc(self):
    """Lazy-load the workspace resource."""
    if self.__workspace_svc is None:
      self.__workspace_svc = self.duplo.load("workspace")
    return self.__workspace_svc

  @property
  def _environment_svc(self):
    """Lazy-load the environment resource."""
    if self.__environment_svc is None:
      self.__environment_svc = self.duplo.load("environment")
    return self.__environment_svc

  @property
  def _resource_group_svc(self):
    """Lazy-load the resource_group resource."""
    if self.__resource_group_svc is None:
      self.__resource_group_svc = self.duplo.load("resource_group")
    return self.__resource_group_svc

  def _items(self, response: dict) -> list:
    """Unwrap a paginated list envelope ``{data: {items: [...]}}``."""
    return response.get("data", {}).get("items", [])

  def _data(self, response: dict) -> dict:
    """Unwrap a single-object envelope ``{success, data: {...}}``."""
    data = response.get("data")
    return data if isinstance(data, dict) else response

  def _id_of(self, obj: dict) -> str:
    """Read an object's id, tolerating either ``id`` or ``Id`` casing."""
    oid = obj.get("id") or obj.get("Id")
    if not oid:
      raise DuploError(
          "The AI HelpDesk response did not include an id.")
    return oid

  def _resolve_workspace_id(self,
                            workspace: str,
                            workspace_id: str,
                            api_version: str) -> str:
    """Resolve a workspace name/id to its id via the workspace resource."""
    return self._id_of(self._workspace_svc.find(
        name=workspace, id=workspace_id, api_version=api_version))

  def _resolve_environment_id(self,
                              workspace_id: str,
                              environment: str,
                              environment_id: str,
                              api_version: str) -> str:
    """Resolve an environment name/id to its id, scoped to the workspace."""
    return self._id_of(self._environment_svc.find(
        name=environment, id=environment_id, workspace_id=workspace_id,
        api_version=api_version))

  def _resolve_env_rg(self,
                      workspace_id: str,
                      environment: str,
                      environment_id: str,
                      resource_group: str,
                      resource_group_id: str,
                      api_version: str) -> tuple:
    """Resolve environment and resource-group names/ids to their ids.

    The resource group is looked up within the resolved environment so a
    name shared across environments stays unambiguous.
    """
    eid = self._resolve_environment_id(
        workspace_id, environment, environment_id, api_version)
    rgid = self._id_of(self._resource_group_svc.find(
        name=resource_group, id=resource_group_id, workspace_id=workspace_id,
        environment_id=eid, api_version=api_version))
    return eid, rgid

  def _record_env_rg(self, record: dict) -> tuple:
    """Read the environment/resource-group ids off a workload record.

    Workload ``update``/``delete``/``update_image`` target the nested
    env/resource-group route, but the record is found at the workspace
    scope — so the ids are taken from its spec rather than asking the
    caller to repeat them.
    """
    spec = record.get("spec") or record.get("Spec") or {}
    eid = spec.get("environmentId") or spec.get("EnvironmentId")
    rgid = spec.get("resourceGroupId") or spec.get("ResourceGroupId")
    if not eid or not rgid:
      raise DuploError(
          "Could not determine the environment/resource-group for the "
          "workload from the AI HelpDesk response.")
    return eid, rgid

  def _base(self, workspace_id: str, api_version: str) -> str:
    """Build the workspace-scoped endpoint for this resource."""
    raise NotImplementedError

  def _find_in_workspace(self,
                         workspace_id: str,
                         name: str,
                         id: str,
                         api_version: str,
                         where: callable = None) -> dict:
    """Find a resource by id or name within an already-resolved workspace.

    With ``id`` the resource is fetched directly from ``_base``.
    Otherwise the server-side ``filters[name]`` list is narrowed and
    matched case-insensitively; ``where`` further restricts the name
    match (e.g. to one environment).
    """
    base = self._base(workspace_id, api_version)
    if id:
      obj = self._data(self.client.get(f"{base}/{quote_plus(id)}").json())
      if not (obj.get("id") or obj.get("Id")):
        raise DuploNotFound(id, self.kind)
      return obj

    if not name:
      raise DuploError("Either a name or --id is required")

    response = self.client.get(
        f"{base}?filters[name]={quote_plus(name)}").json()
    target = name.lower()
    match = next((o for o in self._items(response)
                  if (o.get("name") or o.get("Name") or "").lower() == target
                  and (where is None or where(o))),
                 None)
    if not match:
      raise DuploNotFound(name, self.kind)
    return match
