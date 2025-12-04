import requests
from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("argo_wf")
class DuploArgoWorkflow(DuploResource):
  """Resource for creating and managing Argo Workflow resources in DuploCloud.

  This resource provides commands to interact with Argo Workflows via the DuploCloud proxy.
  It handles the two-step authentication: first obtaining an Argo token from Duplo, then
  using that token to communicate with the Argo Workflow API.

  Usage: Basic CLI Use
    ```sh
    duploctl argo_wf <action>
    ```
  """

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self._tenant = None
    self._tenant_id = None
    self._argo_auth = None
    self._system_info = None
    self._infra_config = None
    self.tenant_svc = duplo.load('tenant')
    self.infra_svc = duplo.load('infrastructure')

  @property
  def tenant(self):
    if not self._tenant:
      self._tenant = self.tenant_svc.find()
      self._tenant_id = self._tenant["TenantId"]
    return self._tenant

  @property
  def tenant_id(self):
    if not self._tenant_id:
      if self.duplo.tenantid:
        self._tenant_id = self.duplo.tenantid
      else:
        self._tenant_id = self.tenant["TenantId"]
    return self._tenant_id

  @property
  def namespace(self):
    prefix = self._get_resource_prefix()
    return f"{prefix}-{self.tenant['AccountName']}"

  def _ensure_argo_enabled(self):
    """Check if Argo Workflows feature is enabled for the tenant's infrastructure.

    Raises:
      DuploError: If Argo Workflows is not enabled (DuploCiTenant not configured).
    """
    if self._infra_config is None:
      plan_id = self.tenant.get("PlanID")
      if not plan_id:
        raise DuploError("Tenant has no associated infrastructure plan", 400)
      self._infra_config = self.infra_svc.find(plan_id)

    # DuploCiTenant is in CustomData array as {"Key": "DuploCiTenant", "Value": "..."}
    custom_data = self._infra_config.get("CustomData", [])
    ci_tenant = next(
      (item.get("Value") for item in custom_data if item.get("Key") == "DuploCiTenant"),
      None
    )
    if not ci_tenant:
      raise DuploError(
        "Argo Workflows is not enabled for this infrastructure. "
        "Please contact administrator.",
        400
      )

  def _get_resource_prefix(self) -> str:
    """Get the resource name prefix from system info.

    Returns:
      str: The resource name prefix (e.g., 'duploservices', 'msi')
    """
    if self._system_info is None:
      response = self.duplo.get("v3/features/system")
      self._system_info = response.json()
    return self._system_info.get("ResourceNamePrefix", "duploservices")

  def _get_argo_auth(self) -> dict:
    """Get Argo Workflow authentication token.

    Makes a POST call to the Duplo API to obtain an Argo Workflow token and admin status.
    The response includes a Kubernetes token for Argo API calls.

    Returns:
      dict: Authentication info containing Token, IsAdmin, TenantId, ExpiresAt

    Raises:
      DuploError: If Argo Workflows is not enabled for the infrastructure.
    """
    if self._argo_auth is None:
      self._ensure_argo_enabled()
      path = f"v3/auth/argo-wf/{self.tenant_id}/admin"
      response = self.duplo.post(path)
      self._argo_auth = response.json()
    return self._argo_auth

  def _argo_request(self, method: str, path: str, data: dict = None) -> dict:
    """Make a request to the Argo Workflow API.

    Uses the Argo token obtained from Duplo for authentication, and also
    passes the Duplo token in the 'duplotoken' header.

    Args:
      method: HTTP method (GET, POST, PUT, DELETE)
      path: API path (e.g., 'workflow-templates/namespace')
      data: Optional request body for POST/PUT

    Returns:
      dict: JSON response from the Argo API
    """
    auth = self._get_argo_auth()
    argo_tenant_id = auth["TenantId"]  # Tenant where workflow controller runs
    argo_token = auth["Token"]

    url = f"{self.duplo.host}/argo-wf/{argo_tenant_id}/api/v1/{path}?current_tenant_id={self.tenant_id}"
    headers = {
      'Content-Type': 'application/json',
      'Authorization': f'Bearer {argo_token}',
      'duplotoken': self.duplo.token
    }

    response = requests.request(
      method=method,
      url=url,
      headers=headers,
      json=data,
      timeout=self.duplo.timeout
    )

    if response.status_code == 404:
      raise DuploError("Argo resource not found", 404)
    if response.status_code == 401:
      raise DuploError("Unauthorized: Invalid or expired Argo token", 401)
    if response.status_code == 403:
      raise DuploError("Forbidden: Insufficient permissions for Argo operation", 403)
    if not (200 <= response.status_code < 300):
      raise DuploError(f"Argo API error: {response.text}", response.status_code)

    return response.json()

  @Command()
  def auth(self) -> dict:
    """Get Argo Authentication Info

    Retrieve the Argo Workflow authentication token and admin status for the current tenant.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf auth
      ```
    Returns:
      dict: Authentication info with Token, IsAdmin, TenantId, ExpiresAt
    """
    return self._get_argo_auth()

  @Command()
  def list_templates(self) -> list:
    """List Workflow Templates

    Retrieve a list of all workflow templates in the current tenant/namespace.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf list_templates
      ```

    Returns:
      list: A list of workflow templates.
    """
    path = f"workflow-templates/{self.namespace}"
    return self._argo_request("GET", path)

  @Command()
  def get_template(self, name: args.NAME) -> dict:
    """Get Workflow Template

    Retrieve a specific workflow template by name.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf get_template <name>
      ```

    Args:
      name: The name of the workflow template.

    Returns:
      dict: The workflow template object.
    """
    path = f"workflow-templates/{self.namespace}/{name}"
    return self._argo_request("GET", path)

  @Command()
  def list_workflows(self) -> list:
    """List Workflows

    Retrieve a list of all workflows in the current tenant/namespace.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf list_workflows
      ```

    Returns:
      list: A list of workflows.
    """
    path = f"workflows/{self.namespace}"
    return self._argo_request("GET", path)

  @Command()
  def get_workflow(self, name: args.NAME) -> dict:
    """Get Workflow

    Retrieve a specific workflow by name.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf get_workflow <name>
      ```

    Args:
      name: The name of the workflow.

    Returns:
      dict: The workflow object.
    """
    path = f"workflows/{self.namespace}/{name}"
    return self._argo_request("GET", path)

  @Command()
  def submit(self, body: args.BODY) -> dict:
    """Submit Workflow

    Submit a new workflow from a workflow spec.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf submit -f workflow.yaml
      ```
      Contents of the `workflow.yaml` file
      ```yaml
      --8<-- "src/tests/data/argo_workflow.yaml"
      ```

    Args:
      body: The workflow specification.

    Returns:
      dict: The created workflow object.
    """
    path = f"workflows/{self.namespace}"
    return self._argo_request("POST", path, body)

  @Command()
  def delete_workflow(self, name: args.NAME) -> dict:
    """Delete Workflow

    Delete a workflow by name.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf delete_workflow <name>
      ```

    Args:
      name: The name of the workflow to delete.

    Returns:
      dict: Deletion confirmation.
    """
    path = f"workflows/{self.namespace}/{name}"
    return self._argo_request("DELETE", path)

  @Command()
  def create_template(self, body: args.BODY) -> dict:
    """Create Workflow Template

    Create a new workflow template.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf create_template -f template.yaml
      ```
      Contents of the `template.yaml` file
      ```yaml
      --8<-- "src/tests/data/argo_wf_template.yaml"
      ```

    Args:
      body: The workflow template specification.

    Returns:
      dict: The created workflow template object.
    """
    path = f"workflow-templates/{self.namespace}"
    return self._argo_request("POST", path, body)

  @Command()
  def delete_template(self, name: args.NAME) -> dict:
    """Delete Workflow Template

    Delete a workflow template by name.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf delete_template <name>
      ```

    Args:
      name: The name of the workflow template to delete.

    Returns:
      dict: Deletion confirmation.
    """
    path = f"workflow-templates/{self.namespace}/{name}"
    return self._argo_request("DELETE", path)