import json
from duplocloud.commander import Command, Resource
from duplocloud.controller import DuploCtl
from duplocloud.resource import DuploResource
from duplocloud.errors import DuploError
import duplocloud.args as args


def _namespace(resource) -> str:
  """K8s namespace derived from tenant prefix (strips trailing dash)."""
  return resource.prefix.rstrip("-")


_STATUS_VERBOSE_KEYS = frozenset(
  {"nodes", "storedTemplates", "storedWorkflowTemplateSpec"}
)


def _ensure_namespace(body: dict, key: str, ns: str) -> None:
  """Inject namespace into a resource body if not already set.

  If the body metadata already contains a namespace the caller is
  responsible for its correctness. When absent it is derived from the
  tenant prefix so the Argo API URL path and body always agree.

  Args:
    body: The resource body dict (mutated in place).
    key: Top-level key for the resource (e.g. "workflow", "template").
    ns: The namespace to inject.

  Raises:
    DuploError: If body is not a dict (e.g. omitted -f/--cli-input).
  """
  if not isinstance(body, dict):
    raise DuploError(
      "Body is required; pass -f/--cli-input with a YAML/JSON object", 400
    )
  meta = body.setdefault(key, {}).setdefault("metadata", {})
  if not meta.get("namespace"):
    meta["namespace"] = ns


@Resource("argo_wf", scope="tenant", client="argo_wf")
class DuploArgoWorkflow(DuploResource):
  """Manage Argo Workflows in DuploCloud.

  Provides commands to list, get, submit, delete, apply, and retrieve
  logs for Argo Workflows via the DuploCloud proxy.

  Usage: Basic CLI Use
    ```sh
    duploctl argo_wf <action>
    ```
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)

  @Command("list_workflows")
  def list(self) -> dict:
    """List Workflows

    Retrieve all workflows in the current tenant namespace.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf list
      ```

    Example: List workflow names only
      ```bash
      duploctl argo_wf list --query "items[*].metadata.name"
      ```

    Returns:
      workflows: A dict containing the list of Argo workflows.
    """
    return self.client.get(
      f"workflows/{_namespace(self)}", self.tenant_id
    ).json()

  @Command("get", "get_workflow")
  def find(self, name: args.NAME) -> dict:
    """Get Workflow

    Find a specific workflow by name.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf find <name>
      ```

    Example: Get workflow phase
      ```bash
      duploctl argo_wf find my-workflow --query "status.phase"
      ```

    Args:
      name: The name of the workflow.

    Returns:
      workflow: The full workflow object.
    """
    safe_name = self.client.sanitize_path_segment(name)
    return self.client.get(
      f"workflows/{_namespace(self)}/{safe_name}", self.tenant_id
    ).json()

  @Command("submit")
  def create(self, body: args.BODY) -> dict:
    """Create Workflow

    Submit a new Argo Workflow from a specification.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf create -f workflow.yaml
      ```
      Contents of the `workflow.yaml` file
      ```yaml
      --8<-- "src/tests/data/argo_workflow.yaml"
      ```

    Args:
      body: The workflow specification.

    Returns:
      workflow: The created workflow object.
    """
    ns = _namespace(self)
    _ensure_namespace(body, "workflow", ns)
    return self.client.post(
      f"workflows/{ns}", self.tenant_id, body
    ).json()

  @Command("delete_workflow")
  def delete(self, name: args.NAME) -> dict:
    """Delete Workflow

    Delete a workflow by name.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf delete <name>
      ```

    Args:
      name: The name of the workflow to delete.

    Returns:
      result: Deletion confirmation.
    """
    safe_name = self.client.sanitize_path_segment(name)
    response = self.client.delete(
      f"workflows/{_namespace(self)}/{safe_name}", self.tenant_id
    )
    return response.json() if response.content else {}

  @Command()
  def apply(self, body: args.BODY) -> dict:
    """Apply Workflow

    Create a workflow if it does not exist. Raises an error if it already
    exists since Argo Workflows are immutable once created. If
    metadata.generateName is set, a new workflow is always created.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf apply -f workflow.yaml
      ```
      Contents of the `workflow.yaml` file
      ```yaml
      --8<-- "src/tests/data/argo_workflow.yaml"
      ```

    Args:
      body: The workflow specification.

    Returns:
      workflow: The created workflow object.

    Raises:
      DuploError: If the workflow already exists (immutable).
    """
    name = body.get("workflow", {}).get("metadata", {}).get("name")
    if name:
      try:
        self.find(name)
        raise DuploError(
          f"Workflow '{name}' already exists. Argo Workflows are "
          "immutable once created. Delete it first or use a new name.",
          409,
        )
      except DuploError as e:
        if e.code != 404:
          raise
    return self.create(body)

  @Command()
  def status(self, name: args.NAME) -> dict:
    """Get Workflow Status

    Retrieve the status of a workflow including phase, progress, and timing.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf status <name>
      ```

    Example: Get just the phase
      ```bash
      duploctl argo_wf status <name> --query "phase"
      ```

    Args:
      name: The name of the workflow.

    Returns:
      status: The workflow status object.
    """
    workflow = self.find(name)
    return {
      k: v
      for k, v in workflow.get("status", {}).items()
      if k not in _STATUS_VERBOSE_KEYS
    }

  @Command()
  def logs(self, name: args.NAME, stream: args.STREAM = False) -> list:
    """Get Workflow Logs

    Retrieve log entries for all pods in a workflow. By default, returns
    existing logs immediately (logOptions.follow=false). Pass --stream to
    follow the log stream until the workflow completes.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf logs <name>
      ```

    Example: Print only log content lines
      ```bash
      duploctl argo_wf logs <name> --query "[*].result.content"
      ```

    Example: Follow live logs
      ```bash
      duploctl argo_wf logs <name> --stream
      ```

    Args:
      name: The name of the workflow.
      stream: Follow the log stream until the workflow completes.

    Returns:
      logs: List of log entry objects from the workflow pods.
    """
    safe_name = self.client.sanitize_path_segment(name)
    params = {"logOptions.container": "main"}
    if not stream:
      params["logOptions.follow"] = "false"
    response = self.client.get(
      f"workflows/{_namespace(self)}/{safe_name}/log",
      self.tenant_id,
      stream=True,
      params=params,
    )
    entries = []
    try:
      for line in response.iter_lines(decode_unicode=True):
        line = line.strip()
        if not line:
          continue
        try:
          entries.append(json.loads(line))
        except json.JSONDecodeError:
          entries.append({"content": line})
    finally:
      response.close()
    return entries


@Resource("argo_wf_template", scope="tenant", client="argo_wf")
class DuploArgoWorkflowTemplate(DuploResource):
  """Manage Argo Workflow Templates in DuploCloud.

  Provides commands to list, get, create, update, delete, and apply
  Argo Workflow Templates via the DuploCloud proxy.

  Usage: Basic CLI Use
    ```sh
    duploctl argo_wf_template <action>
    ```
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)

  @Command()
  def list(self) -> dict:
    """List Workflow Templates

    Retrieve all workflow templates in the current tenant namespace.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf_template list
      ```

    Example: List template names only
      ```bash
      duploctl argo_wf_template list --query "items[*].metadata.name"
      ```

    Returns:
      templates: A dict containing the list of Argo workflow templates.
    """
    return self.client.get(
      f"workflow-templates/{_namespace(self)}", self.tenant_id
    ).json()

  @Command()
  def find(self, name: args.NAME) -> dict:
    """Get Workflow Template

    Find a specific workflow template by name.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf_template find <name>
      ```

    Example: Get template entrypoint
      ```bash
      duploctl argo_wf_template find my-template --query "spec.entrypoint"
      ```

    Args:
      name: The name of the workflow template.

    Returns:
      template: The full workflow template object.
    """
    safe_name = self.client.sanitize_path_segment(name)
    return self.client.get(
      f"workflow-templates/{_namespace(self)}/{safe_name}", self.tenant_id
    ).json()

  @Command()
  def create(self, body: args.BODY) -> dict:
    """Create Workflow Template

    Create a new Argo Workflow Template.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf_template create -f template.yaml
      ```
      Contents of the `template.yaml` file
      ```yaml
      --8<-- "src/tests/data/argo_wf_template.yaml"
      ```

    Args:
      body: The workflow template specification.

    Returns:
      template: The created workflow template object.
    """
    ns = _namespace(self)
    _ensure_namespace(body, "template", ns)
    return self.client.post(
      f"workflow-templates/{ns}", self.tenant_id, body
    ).json()

  @Command()
  def update(self, body: args.BODY) -> dict:
    """Update Workflow Template

    Update an existing Argo Workflow Template. Fetches the current
    resourceVersion and merges it into the body before submitting.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf_template update -f template.yaml
      ```
      Contents of the `template.yaml` file
      ```yaml
      --8<-- "src/tests/data/argo_wf_template.yaml"
      ```

    Args:
      body: The workflow template specification with name in metadata.

    Returns:
      template: The updated workflow template object.

    Raises:
      DuploError: If the template name is missing from metadata.
    """
    ns = _namespace(self)
    _ensure_namespace(body, "template", ns)
    name = body.get("template", {}).get("metadata", {}).get("name")
    if not name:
      raise DuploError(
        "Template name is required in metadata for update", 400
      )
    current = self.find(name)
    resource_version = current.get("metadata", {}).get("resourceVersion")
    if resource_version:
      body["template"]["metadata"]["resourceVersion"] = resource_version
    safe_name = self.client.sanitize_path_segment(name)
    return self.client.put(
      f"workflow-templates/{ns}/{safe_name}",
      self.tenant_id,
      body,
    ).json()

  @Command()
  def delete(self, name: args.NAME) -> dict:
    """Delete Workflow Template

    Delete a workflow template by name.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf_template delete <name>
      ```

    Args:
      name: The name of the workflow template to delete.

    Returns:
      result: Deletion confirmation.
    """
    safe_name = self.client.sanitize_path_segment(name)
    response = self.client.delete(
      f"workflow-templates/{_namespace(self)}/{safe_name}", self.tenant_id
    )
    return response.json() if response.content else {}

  @Command()
  def apply(self, body: args.BODY) -> dict:
    """Apply Workflow Template

    Create or update a workflow template. If the template exists it
    will be updated; otherwise a new template is created.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf_template apply -f template.yaml
      ```
      Contents of the `template.yaml` file
      ```yaml
      --8<-- "src/tests/data/argo_wf_template.yaml"
      ```

    Args:
      body: The workflow template specification.

    Returns:
      template: The created or updated workflow template object.
    """
    name = body.get("template", {}).get("metadata", {}).get("name")
    if name:
      try:
        self.find(name)
        return self.update(body)
      except DuploError as e:
        if e.code != 404:
          raise
    return self.create(body)
