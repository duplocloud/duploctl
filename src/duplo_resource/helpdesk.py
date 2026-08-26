import copy
from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.commander import Command
from duplocloud.errors import (
    DuploError, DuploFailedResource, DuploNotFound, DuploStillWaiting)
from duplocloud.resource import DuploResource
from duplo_resource.helpdesk_client import unwrap_data
import duplocloud.args as args

WAITER_DEFAULTS = {
  "status_path": "status",
  "success_state": "Complete",
  "failure_states": {
    "Failed": "provisioning failed",
    "Blocked": "provisioning is blocked",
    "WaitingForApproval": ("provisioning is waiting for manual approval, "
                           "which duploctl cannot provide"),
    "DeprovisionFailed": "deprovisioning failed",
  },
  "failure_detail_path": "blockedReason",
  "ready_path": None,
  "ready_state": None,
  "ready_failure_path": None,
  "ready_failure_states": {},
  "deprovisioned_state": "DeProvisioned",
  "poll": 10,
  "timeout": 1800,
}
"""Waiter semantics shared with the duploai terraform provider.

A resource's ``status`` reaches ``Complete`` on success; the failure
states abort immediately with the reason at ``blockedReason``. An
optional ready gate (``ready_path``/``ready_state``) requires a second
field to match before the resource counts as ready, and an optional
ready-failure gate (``ready_failure_path``/``ready_failure_states``)
maps values at a third path to terminal failures (e.g. a stalled Helm
release).
``deprovisioned_state`` is the status a resource must reach before its
record can be deleted.
"""


class HelpdeskResource(DuploResource):
  """Shared plumbing for AI HelpDesk resources.

  Consolidates the id-casing tolerance, name→id resolution, and waiter
  behavior shared by all helpdesk resources so it cannot drift between
  them. Two families build on it: the workspace-scoped HDV2 entities
  (environment, resource group, and the workloads), registered with
  ``scope="workspace"`` so the workspace resolves lazily from the
  global ``-W``/``--workspace-id`` flags via the injected
  ``workspace_id`` property, and the portal-scoped admin data-plane
  entities via ``HelpdeskAdminResource``. All requests go through the
  dedicated helpdesk client. Sibling resources used for resolution are
  lazy-loaded so instantiating one resource never eagerly instantiates
  another (or, for ``environment``, itself).
  """

  waiter = None
  """Set to a dict on subclasses to enable ``--wait`` on mutations.

  Keys override ``WAITER_DEFAULTS``; an empty dict takes all defaults.
  ``None`` means the resource is synchronous and never waits.
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)
    self.__environment_svc = None
    self.__resource_group_svc = None

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

  def _id_of(self, obj: dict) -> str:
    """Read an object's id, tolerating either ``id`` or ``Id`` casing."""
    oid = obj.get("id") or obj.get("Id")
    if not oid:
      raise DuploError(
          "The AI HelpDesk response did not include an id.")
    return oid

  def _resolve_environment_id(self,
                              environment: str,
                              environment_id: str) -> str:
    """Resolve an environment name/id to its id via the environment resource."""
    return self._id_of(self._environment_svc.find(
        name=environment, id=environment_id))

  def _resolve_env_rg(self,
                      environment: str,
                      environment_id: str,
                      resource_group: str,
                      resource_group_id: str) -> tuple:
    """Resolve environment and resource-group names/ids to their ids.

    The resource group is looked up within the resolved environment so a
    name shared across environments stays unambiguous.
    """
    eid = self._resolve_environment_id(environment, environment_id)
    rgid = self._id_of(self._resource_group_svc.find(
        name=resource_group, id=resource_group_id, environment_id=eid))
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

  def _base(self) -> str:
    """Build the workspace-scoped endpoint for this resource."""
    raise NotImplementedError

  def _strip_scope_ids(self, body: dict) -> dict:
    """Return a copy of a create body without ``spec.scopeIds``.

    The backend derives scope ids from the parent resource group and
    rejects any caller-supplied value on create, so a record round-tripped
    from ``find`` into ``create``/``apply`` would 400. Stripping them here
    keeps that round-trip working; other fields are sent as provided.
    """
    spec = body.get("spec") or body.get("Spec")
    if not isinstance(spec, dict):
      return body
    if "scopeIds" not in spec and "ScopeIds" not in spec:
      return body
    spec = {k: v for k, v in spec.items()
            if k not in ("scopeIds", "ScopeIds")}
    key = "spec" if "spec" in body else "Spec"
    return {**body, key: spec}

  def _find_in_workspace(self,
                         name: str,
                         id: str,
                         where: callable = None) -> dict:
    """Find a resource by id or name within the current workspace.

    With ``id`` the resource is fetched directly from ``_base``.
    Otherwise the server-side ``filters[name]`` list is narrowed and
    matched case-insensitively; ``where`` further restricts the name
    match (e.g. to one environment).
    """
    base = self._base()
    if id:
      obj = unwrap_data(self.client.get(f"{base}/{quote_plus(id)}").json())
      if not (obj.get("id") or obj.get("Id")):
        raise DuploNotFound(id, self.kind)
      return obj

    if not name:
      raise DuploError("Either a name or --id is required")

    items = self.client.get_items(
        f"{base}?filters[name]={quote_plus(name)}")
    target = name.lower()
    match = next((o for o in items
                  if (o.get("name") or o.get("Name") or "").lower() == target
                  and (where is None or where(o))),
                 None)
    if not match:
      raise DuploNotFound(name, self.kind)
    return match

  def _extract_path(self, obj: dict, path: str):
    """Read a dotted path (e.g. ``result.cloudDetails.state``) off a dict.

    A segment may carry a list selector, e.g.
    ``status.conditions[type=Ready].status`` picks the first list
    element whose ``type`` equals ``Ready`` (the provider's waiter
    syntax for Kubernetes conditions). Returns None when any segment
    is missing or the wrong shape.
    """
    current = obj
    for segment in path.split("."):
      selector = None
      if segment.endswith("]") and "[" in segment:
        segment, _, raw = segment[:-1].partition("[")
        key, _, value = raw.partition("=")
        selector = (key, value)
      if not isinstance(current, dict):
        return None
      current = current.get(segment)
      if selector is not None:
        if not isinstance(current, list):
          return None
        key, value = selector
        current = next(
            (e for e in current
             if isinstance(e, dict) and str(e.get(key)) == value),
            None)
    return current

  def _waiter_config(self) -> dict:
    """The effective waiter settings: class overrides over the defaults."""
    return {**WAITER_DEFAULTS, **(self.waiter or {})}

  def _wait_for_ready(self, rid: str) -> None:
    """Poll a record until its status reaches the waiter's success state.

    Mirrors the duploai terraform provider's waiter: a failure status
    aborts immediately with the ``blockedReason`` detail, and an
    optional ready gate must also match before success. Only called
    when the resource declares a ``waiter``.
    """
    cfg = self._waiter_config()
    path = f"{self._base()}/{quote_plus(rid)}"

    def wait_check():
      record = unwrap_data(self.client.get(path).json())
      status = self._extract_path(record, cfg["status_path"])
      if status in cfg["failure_states"]:
        message = f"{self.kind} '{rid}': {cfg['failure_states'][status]}"
        detail = self._extract_path(record, cfg["failure_detail_path"])
        if detail:
          message = f"{message}: {detail}"
        raise DuploFailedResource(message)
      if status != cfg["success_state"]:
        raise DuploStillWaiting(
            f"{self.kind} '{rid}' has status '{status}'")
      if cfg["ready_failure_path"] is not None:
        failed = self._extract_path(record, cfg["ready_failure_path"])
        if failed in cfg["ready_failure_states"]:
          message = (f"{self.kind} '{rid}': "
                     f"{cfg['ready_failure_states'][failed]}")
          detail = self._extract_path(record, cfg["failure_detail_path"])
          if detail:
            message = f"{message}: {detail}"
          raise DuploFailedResource(message)
      if cfg["ready_path"] is not None:
        ready = self._extract_path(record, cfg["ready_path"])
        if ready != cfg["ready_state"]:
          raise DuploStillWaiting(
              f"{self.kind} '{rid}' is complete but not ready "
              f"({cfg['ready_path']} is '{ready}')")

    self.wait(wait_check, cfg["timeout"], cfg["poll"])

  def _wait_for_deprovisioned(self, rid: str) -> None:
    """Poll a record until it reaches the deprovisioned state (or is gone).

    Resources with cloud infra cannot be deleted while live: the
    deprovision call starts the teardown, and the record only becomes
    deletable at ``deprovisioned_state``. A record that disappears
    mid-wait counts as done; ``DeprovisionFailed`` (via the failure
    states) aborts.
    """
    cfg = self._waiter_config()
    path = f"{self._base()}/{quote_plus(rid)}"

    def wait_check():
      try:
        record = unwrap_data(self.client.get(path).json())
      except DuploNotFound:
        return
      if not (record.get("id") or record.get("Id")):
        return
      status = self._extract_path(record, cfg["status_path"])
      if status in cfg["failure_states"]:
        message = f"{self.kind} '{rid}': {cfg['failure_states'][status]}"
        detail = self._extract_path(record, cfg["failure_detail_path"])
        if detail:
          message = f"{message}: {detail}"
        raise DuploFailedResource(message)
      if status != cfg["deprovisioned_state"]:
        raise DuploStillWaiting(
            f"{self.kind} '{rid}' is deprovisioning (status '{status}')")

    self.wait(wait_check, cfg["timeout"], cfg["poll"])

  def _wait_until_gone(self, rid: str) -> None:
    """Poll until the record no longer exists.

    The delete call on asynchronously-provisioned resources only starts
    the removal — this confirms the record actually disappeared.
    """
    cfg = self._waiter_config()
    path = f"{self._base()}/{quote_plus(rid)}"

    def wait_check():
      try:
        record = unwrap_data(self.client.get(path).json())
      except DuploNotFound:
        return
      if not (record.get("id") or record.get("Id")):
        return
      status = self._extract_path(record, cfg["status_path"])
      if status in cfg["failure_states"]:
        message = f"{self.kind} '{rid}': {cfg['failure_states'][status]}"
        detail = self._extract_path(record, cfg["failure_detail_path"])
        if detail:
          message = f"{message}: {detail}"
        raise DuploFailedResource(message)
      raise DuploStillWaiting(
          f"{self.kind} '{rid}' still exists (status '{status}')")

    self.wait(wait_check, cfg["timeout"], cfg["poll"])


class HelpdeskAdminResource(HelpdeskResource):
  """Generic CRUD over an AI HelpDesk admin data collection.

  The admin data plane is a set of flat, synchronous collections under
  ``admin/data/<Collection>`` sharing identical CRUD semantics, so each
  concrete entity is a subclass that only names its ``collection``
  (copied verbatim from the backend, casing included). Updates are full
  replaces and always carry the record ``id`` in the body: the backend
  deserializes the body into its entity model, whose id self-generates
  when absent, making the uniqueness check collide with the record
  itself.
  """

  collection = None
  read_after_write = False
  """Re-read the record after create when the create response differs
  from the canonical read (e.g. providers)."""

  def _base(self) -> str:
    """Build the admin endpoint for this collection."""
    return f"admin/data/{self.collection}"

  @Command("ls")
  def list(self) -> list:
    """List all records in this collection.

    Usage: CLI Usage
      ```sh
      duploctl {{command}} list
      ```

    Returns:
      resources: All records, across pages.
    """
    return self.client.get_items(self._base())

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None) -> dict:
    """Find a record by name or id.

    With ``--id`` the record is fetched directly; otherwise it is
    matched by name (case-insensitive).

    Usage: CLI Usage
      ```sh
      duploctl {{command}} find <name>
      duploctl {{command}} find --id <id>
      ```

    Args:
      name: The record name.
      id: The record id. Skips the name lookup when provided.

    Returns:
      resource: The matching record.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no record matches.
    """
    return self._find_in_workspace(name, id)

  @Command()
  def create(self, body: args.BODY) -> dict:
    """Create a record.

    Usage: CLI Usage
      ```sh
      duploctl {{command}} create -f resource.yaml
      ```

    Args:
      body: The record definition.

    Returns:
      resource: The created record.

    Raises:
      DuploError: If no body is provided.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    record = unwrap_data(self.client.post(self._base(), body).json())
    rid = self._id_of(record)
    if self.read_after_write:
      record = unwrap_data(
          self.client.get(f"{self._base()}/{quote_plus(rid)}").json())
    if self.duplo.wait and self.waiter is not None:
      self._wait_for_ready(rid)
    return record

  @Command()
  def update(self,
             body: args.BODY = None,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Update a record.

    The target is resolved by ``--id``, ``name``, or the body's
    ``name`` field, in that order. The update is a full replace —
    fields omitted from the body are cleared — and the name is
    immutable.

    Usage: CLI Usage
      ```sh
      duploctl {{command}} update <name> -f resource.yaml
      duploctl {{command}} update -f resource.yaml
      ```

    Args:
      body: The record definition to apply.
      name: The record name. Defaults to the body's ``name``.
      id: The record id. Skips the name lookup when provided.

    Returns:
      resource: The updated record.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the record cannot be found.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    rid = id or self._id_of(
        self.find(name=name or body.get("name") or body.get("Name")))
    key = "Id" if "Id" in body else "id"
    payload = {**body, key: rid}
    record = unwrap_data(self.client.put(
        f"{self._base()}/{quote_plus(rid)}", payload).json())
    if self.duplo.wait and self.waiter is not None:
      self._wait_for_ready(rid)
    return record

  @Command()
  def apply(self, body: args.BODY) -> dict:
    """Create or update a record.

    Looks the record up by the body's ``name``: updates it when it
    exists, creates it otherwise.

    Usage: CLI Usage
      ```sh
      duploctl {{command}} apply -f resource.yaml
      ```

    Args:
      body: The record definition to apply.

    Returns:
      resource: The created or updated record.

    Raises:
      DuploError: If no body is provided.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    name = body.get("name") or body.get("Name")
    if not name:
      raise DuploError("The body must include a 'name' field for apply")
    try:
      existing = self.find(name=name)
    except DuploNotFound:
      return self.create(body=body)
    return self.update(body=body, id=self._id_of(existing))

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Delete a record.

    Usage: CLI Usage
      ```sh
      duploctl {{command}} delete <name>
      duploctl {{command}} delete --id <id>
      ```

    Args:
      name: The record name.
      id: The record id. Skips the name lookup when provided.

    Returns:
      message: A deletion confirmation.

    Raises:
      DuploNotFound: If the record cannot be found.
    """
    rid = id or self._id_of(self.find(name=name))
    self.client.delete(f"{self._base()}/{quote_plus(rid)}")
    return {"message": f"{self.kind} '{name or rid}' deleted"}


class HelpdeskWorkspaceResource(HelpdeskResource):
  """Generic CRUD over a workspace-scoped AI HelpDesk user collection.

  The user data plane hangs asynchronous, cloud-backed collections
  under ``user/data/workspaces/{workspace_id}/environment/<Collection>``
  with shared semantics, so each concrete entity is a subclass that
  names its ``collection`` (casing copied verbatim from the backend)
  and declares its quirks:

  - ``request_constants``: dotted-path fields the backend requires on
    every create/update (e.g. ``spec.k8sResource.kind``), injected only
    when the body doesn't already set them so round-trips never
    clobber.
  - ``immutable``: the backend has no update route — ``update`` (and an
    ``apply`` over an existing record) fail with guidance to delete and
    recreate.
  - ``deprovision``: cloud-backed records cannot be deleted while
    live — ``delete`` first posts ``/{id}/deprovision`` and waits for
    the deprovisioned state before issuing the delete. This wait is
    integral to delete, not gated on ``--wait``; ``--wait``
    additionally confirms the record is gone afterwards.

  These are the duploai terraform provider's endpoint semantics; the
  waiter (``--wait`` on create/update) polls status to ``Complete``
  with the provider's failure and ready-gate handling.
  """

  collection = None
  segment = "environment"
  request_constants = {}
  immutable = False
  deprovision = True
  waiter = {}

  def _base(self) -> str:
    """Build the workspace-scoped endpoint for this collection."""
    return (f"user/data/workspaces/{quote_plus(self.workspace_id)}/"
            f"{self.segment}/{self.collection}")

  def _with_constants(self, body: dict, rid: str = None) -> dict:
    """Return a copy of the body with required constants (and id) set.

    Constants only fill absent fields — a caller-supplied value always
    wins. The record id is included on updates to match the admin-plane
    contract (the backend's uniqueness check can collide with the
    record itself when the body carries no id).
    """
    payload = copy.deepcopy(body)
    for path, value in self.request_constants.items():
      target = payload
      parts = path.split(".")
      for part in parts[:-1]:
        nxt = target.get(part)
        if not isinstance(nxt, dict):
          nxt = {}
          target[part] = nxt
        target = nxt
      target.setdefault(parts[-1], value)
    if rid is not None and "Id" not in payload:
      payload.setdefault("id", rid)
    return payload

  @Command("ls")
  def list(self) -> list:
    """List all records in this collection for the workspace.

    Usage: CLI Usage
      ```sh
      duploctl {{command}} list
      ```

    Returns:
      resources: All records, across pages.
    """
    return self.client.get_items(self._base())

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None) -> dict:
    """Find a record by name or id.

    With ``--id`` the record is fetched directly; otherwise it is
    matched by name (case-insensitive).

    Usage: CLI Usage
      ```sh
      duploctl {{command}} find <name>
      duploctl {{command}} find --id <id>
      ```

    Args:
      name: The record name.
      id: The record id. Skips the name lookup when provided.

    Returns:
      resource: The matching record.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no record matches.
    """
    return self._find_in_workspace(name, id)

  @Command()
  def create(self, body: args.BODY) -> dict:
    """Create a record.

    Provisioning is asynchronous: the response carries the accepted
    record; pass ``--wait`` to poll until it is ready.

    Usage: CLI Usage
      ```sh
      duploctl {{command}} create -f resource.yaml
      duploctl {{command}} create -f resource.yaml --wait
      ```

    Args:
      body: The record definition.

    Returns:
      resource: The created record.

    Raises:
      DuploError: If no body is provided.
      DuploFailedResource: If ``--wait`` is set and provisioning fails.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    payload = self._with_constants(body)
    record = unwrap_data(self.client.post(self._base(), payload).json())
    rid = self._id_of(record)
    if self.duplo.wait and self.waiter is not None:
      self._wait_for_ready(rid)
      # the create response predates provisioning — return the live
      # record so the caller sees the final status
      record = self._find_in_workspace(None, rid)
    return record

  @Command()
  def update(self,
             body: args.BODY = None,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Update a record.

    The target is resolved by ``--id``, ``name``, or the body's
    ``name`` field, in that order. The update is a full replace.

    Usage: CLI Usage
      ```sh
      duploctl {{command}} update <name> -f resource.yaml
      duploctl {{command}} update -f resource.yaml --wait
      ```

    Args:
      body: The record definition to apply.
      name: The record name. Defaults to the body's ``name``.
      id: The record id. Skips the name lookup when provided.

    Returns:
      resource: The updated record.

    Raises:
      DuploError: If no body is provided, or the resource is immutable.
      DuploNotFound: If the record cannot be found.
    """
    if self.immutable:
      raise DuploError(
          f"{self.kind} is immutable: delete and recreate it instead", 400)
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    rid = id or self._id_of(
        self.find(name=name or body.get("name") or body.get("Name")))
    payload = self._with_constants(body, rid)
    record = unwrap_data(self.client.put(
        f"{self._base()}/{quote_plus(rid)}", payload).json())
    if self.duplo.wait and self.waiter is not None:
      self._wait_for_ready(rid)
      # the update response predates re-provisioning — return the live
      # record so the caller sees the final status
      record = self._find_in_workspace(None, rid)
    return record

  @Command()
  def apply(self, body: args.BODY) -> dict:
    """Create or update a record.

    Looks the record up by the body's ``name``: updates it when it
    exists, creates it otherwise. Immutable resources cannot be
    updated, so an apply over an existing record fails.

    Usage: CLI Usage
      ```sh
      duploctl {{command}} apply -f resource.yaml
      ```

    Args:
      body: The record definition to apply.

    Returns:
      resource: The created or updated record.

    Raises:
      DuploError: If no body is provided, the body has no name, or an
        immutable record already exists.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    name = body.get("name") or body.get("Name")
    if not name:
      raise DuploError("The body must include a 'name' field for apply")
    try:
      existing = self.find(name=name)
    except DuploNotFound:
      return self.create(body=body)
    if self.immutable:
      raise DuploError(
          f"{self.kind} '{name}' already exists and is immutable: "
          "delete and recreate it instead", 400)
    return self.update(body=body, id=self._id_of(existing))

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Delete a record, deprovisioning its cloud resources first.

    Cloud-backed records cannot be deleted while live: this posts the
    deprovision step, waits for the deprovisioned state, then issues
    the delete. ``--wait`` additionally confirms the record is gone.

    Usage: CLI Usage
      ```sh
      duploctl {{command}} delete <name>
      duploctl {{command}} delete --id <id> --wait
      ```

    Args:
      name: The record name.
      id: The record id. Skips the name lookup when provided.

    Returns:
      message: A deletion confirmation.

    Raises:
      DuploNotFound: If the record cannot be found.
      DuploFailedResource: If deprovisioning fails.
    """
    rid = id or self._id_of(self.find(name=name))
    base = self._base()
    if self.deprovision:
      try:
        self.client.post(f"{base}/{quote_plus(rid)}/deprovision")
      except DuploNotFound:
        pass  # already deprovisioned (or never provisioned) — proceed
      self._wait_for_deprovisioned(rid)
    try:
      self.client.delete(f"{base}/{quote_plus(rid)}")
    except DuploNotFound:
      pass  # vanished between the wait and the delete — that's the goal
    if self.duplo.wait and self.waiter is not None:
      self._wait_until_gone(rid)
    return {"message": f"{self.kind} '{name or rid}' deleted"}
