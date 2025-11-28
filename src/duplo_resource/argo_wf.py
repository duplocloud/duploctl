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
    self.tenant_svc = duplo.load('tenant')

  @property
  def tenant(self):
    """Get the current tenant."""
    if not self._tenant:
      self._tenant = self.tenant_svc.find()
      self._tenant_id = self._tenant["TenantId"]
    return self._tenant

  @property
  def tenant_id(self):
    """Get the current tenant ID."""
    if not self._tenant_id:
      if self.duplo.tenantid:
        self._tenant_id = self.duplo.tenantid
      else:
        self._tenant_id = self.tenant["TenantId"]
    return self._tenant_id

  @property
  def namespace(self):
    """Get the Kubernetes namespace for the current tenant using system prefix."""
    prefix = self.get_resource_prefix()
    return f"{prefix}-{self.tenant['AccountName']}"

  def get_resource_prefix(self) -> str:
    """Get the resource name prefix from system info.

    Returns:
      str: The resource name prefix (e.g., 'duploservices', 'msi')
    """
    if self._system_info is None:
      response = self.duplo.get("v3/features/system")
      self._system_info = response.json()
    return self._system_info.get("ResourceNamePrefix", "duploservices")

  def get_argo_auth(self) -> dict:
    """Get Argo Workflow authentication token.

    Makes a POST call to the Duplo API to obtain an Argo Workflow token and admin status.
    The response includes a Kubernetes token for Argo API calls.

    Returns:
      dict: Authentication info containing Token, IsAdmin, TenantId, ExpiresAt
    """
    if self._argo_auth is None:
      path = f"v3/auth/argo-wf/{self.tenant_id}/admin"
      response = self.duplo.post(path)
      self._argo_auth = response.json()
    return self._argo_auth

  def argo_request(self, method: str, path: str, data: dict = None) -> dict:
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
    auth = self.get_argo_auth()
    argo_tenant_id = auth["TenantId"]  # Tenant where workflow controller runs
    argo_token = auth["Token"]

    url = f"{self.duplo.host}/argo-wf/{argo_tenant_id}/api/v1/{path}"
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
    return self.get_argo_auth()

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
    return self.argo_request("GET", path)

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
    return self.argo_request("GET", path)

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
    return self.argo_request("GET", path)

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
    return self.argo_request("GET", path)

  @Command()
  def submit(self, body: args.BODY) -> dict:
    """Submit Workflow

    Submit a new workflow from a workflow spec.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf submit -f workflow.yaml
      ```

    Args:
      body: The workflow specification.

    Returns:
      dict: The created workflow object.
    """
    path = f"workflows/{self.namespace}"
    return self.argo_request("POST", path, body)

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
    return self.argo_request("DELETE", path)

  @Command()
  def create_template(self, body: args.BODY) -> dict:
    """Create Workflow Template

    Create a new workflow template.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf create_template -f template.yaml
      ```

    Args:
      body: The workflow template specification.

    Returns:
      dict: The created workflow template object.
    """
    path = f"workflow-templates/{self.namespace}"
    return self.argo_request("POST", path, body)

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
    return self.argo_request("DELETE", path)