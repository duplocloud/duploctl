from duplocloud.errors import DuploError
from duplocloud.resource import DuploProxyResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("argo_wf")
class DuploArgoWorkflow(DuploProxyResource):
  """Resource for creating and managing Argo Workflow resources in DuploCloud.

  This resource provides commands to interact with Argo Workflows via the DuploCloud proxy.
  It handles the two-step authentication: first obtaining an Argo token from Duplo, then
  using that token to communicate with the Argo Workflow API.

  Extends DuploProxyResource which provides:
  - Tenant and tenant_id properties with caching
  - Resource prefix and namespace from system info
  - Infrastructure config caching
  - Common proxy request helpers

  Usage: Basic CLI Use
    ```sh
    duploctl argo_wf <action>
    ```
  """

  def _ensure_argo_enabled(self):
    """Check if Argo Workflows feature is enabled for the tenant's infrastructure.

    Uses inherited get_infra_config() for caching.

    Raises:
      DuploError: If Argo Workflows is not enabled (DuploCiTenant not configured).
    """
    infra_config = self.get_infra_config()
    
    # DuploCiTenant is in CustomData array as {"Key": "DuploCiTenant", "Value": "..."}
    custom_data = infra_config.get("CustomData", [])
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

  def _get_proxy_auth(self) -> dict:
    """Get Argo Workflow authentication token.

    Implements DuploProxyResource._get_proxy_auth for Argo-specific auth flow.
    Makes a POST call to the Duplo API to obtain an Argo Workflow token and admin status.
    The response includes a Kubernetes token for Argo API calls.
    
    Checks for token expiration using _is_proxy_auth_expired() and refreshes
    the token if needed.

    Returns:
      dict: Authentication info containing Token, IsAdmin, TenantId, ExpiresAt

    Raises:
      DuploError: If Argo Workflows is not enabled for the infrastructure.
    """
    if self._is_proxy_auth_expired():
      self._ensure_argo_enabled()
      path = f"v3/auth/argo-wf/{self.tenant_id}/admin"
      response = self.duplo.post(path)
      self._proxy_auth = response.json()
    return self._proxy_auth

  def _proxy_request(self, method: str, path: str, data: dict = None) -> dict:
    """Make a request to the Argo Workflow API.

    Implements DuploProxyResource._proxy_request for Argo-specific requests.
    Uses _make_request from base class for consistent error handling.
    Uses the Argo token obtained from Duplo for authentication, and also
    passes the Duplo token in the 'duplotoken' header.

    Args:
      method: HTTP method (GET, POST, PUT, DELETE)
      path: API path (e.g., 'workflow-templates/namespace')
      data: Optional request body for POST/PUT

    Returns:
      dict: JSON response from the Argo API
    """
    auth = self._get_proxy_auth()
    argo_tenant_id = auth["TenantId"]  # Tenant where workflow controller runs
    argo_token = auth["Token"]

    url = f"{self.duplo.host}/argo-wf/{argo_tenant_id}/api/v1/{path}?current_tenant_id={self.tenant_id}"
    headers = self._build_proxy_headers(argo_token, {'duplotoken': self.duplo.token})

    response = self._make_request(
      method=method,
      url=url,
      headers=headers,
      data=data,
      service_name="Argo"
    )
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
    return self._get_proxy_auth()

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
    return self._proxy_request("GET", path)

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
    path = f"workflow-templates/{self.namespace}/{self._sanitize_path_segment(name)}"
    return self._proxy_request("GET", path)

  @Command()
  def list(self) -> list:
    """List Workflows

    Retrieve a list of all workflows in the current tenant/namespace.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf list
      ```

    Returns:
      list: A list of workflows.
    """
    path = f"workflows/{self.namespace}"
    return self._proxy_request("GET", path)

  @Command()
  def get(self, name: args.NAME) -> dict:
    """Get Workflow

    Retrieve a specific workflow by name.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf get <name>
      ```

    Args:
      name: The name of the workflow.

    Returns:
      dict: The workflow object.
    """
    path = f"workflows/{self.namespace}/{self._sanitize_path_segment(name)}"
    return self._proxy_request("GET", path)

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
    return self._proxy_request("POST", path, body)

  @Command()
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
      dict: Deletion confirmation.
    """
    path = f"workflows/{self.namespace}/{self._sanitize_path_segment(name)}"
    return self._proxy_request("DELETE", path)

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
    return self._proxy_request("POST", path, body)

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
    path = f"workflow-templates/{self.namespace}/{self._sanitize_path_segment(name)}"
    return self._proxy_request("DELETE", path)