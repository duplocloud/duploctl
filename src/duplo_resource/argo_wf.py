from duplocloud.errors import DuploError, DuploExpiredCache
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args
import jwt
from datetime import datetime, timezone


class ArgoBase(DuploResource):
  """Base class for Argo Workflow resources.

  Provides shared authentication and proxy request functionality for both
  workflow and workflow template resources.

  Uses DuploResource with enhanced DuploClient methods that support:
  - Custom headers for proxy authentication
  - Path sanitization via DuploClient.sanitize_path_segment()
  """

  def __init__(self, duplo):
    super().__init__(duplo)
    self._infra_config = None
    self.infra_svc = duplo.load('infrastructure')

  @property
  def _namespace(self) -> str:
    """Get K8s namespace from prefix (prefix without trailing dash)."""
    return self.prefix.rstrip('-')

  def _get_infra_config(self, plan_id: str = None) -> dict:
    """Get infrastructure configuration with caching (internal use only).
    
    Fetches infrastructure config for the tenant and caches it. The plan_id
    parameter is optional and used for specific infrastructure plans.
    
    Args:
      plan_id: Optional infrastructure plan ID
      
    Returns:
      dict: Infrastructure configuration
    """
    if self._infra_config is None:
      pid = plan_id or self.tenant.get("PlanID")
      if not pid:
        raise DuploError("Tenant has no associated infrastructure plan", 400)
      self._infra_config = self.infra_svc.find(pid)
    return self._infra_config

  def _ensure_argo_enabled(self):
    """Check if Argo Workflows feature is enabled for the tenant's infrastructure.

    Uses inherited get_infra_config() for caching.

    Raises:
      DuploError: If Argo Workflows is not enabled (DuploCiTenant not configured).
    """
    infra_config = self._get_infra_config()
    
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

  def _get_argo_auth_headers(self) -> dict:
    """Get cached Argo Workflow authentication headers.

    Makes a POST call to the Duplo API to obtain an Argo Workflow JWT token.
    Returns the headers needed for Argo API calls with proper caching.
    
    Uses DuploClient's cache system to store the JWT token and refreshes
    it automatically when expired.

    Returns:
      dict: Headers for Argo API calls including Authorization and duplotoken

    Raises:
      DuploError: If Argo Workflows is not enabled for the infrastructure.
    """
    cache_key = self.duplo.cache_key_for("argo-auth")
    
    try:
      # Try to get from cache
      auth_data = self.duplo.get_cached_item(cache_key)
      
      # Check if JWT token is expired (exp is Unix timestamp)
      if "Token" in auth_data:
        try:
          decoded = jwt.decode(auth_data["Token"], options={"verify_signature": False})
          exp = decoded.get("exp")
          if exp:
            # JWT exp is Unix timestamp, compare with current time
            now = datetime.now(timezone.utc).timestamp()
            if now > exp:
              raise DuploExpiredCache(cache_key)
        except jwt.DecodeError:
          # If we can't decode, treat as expired
          raise DuploExpiredCache(cache_key)
      
      # Check the expires at field as fallback
      if self.duplo.expired(auth_data.get("ExpiresAt", None)):
        raise DuploExpiredCache(cache_key)
        
    except (DuploExpiredCache, KeyError):
      # Need to refresh the token
      self._ensure_argo_enabled()
      path = f"v3/auth/argo-wf/{self.tenant_id}/admin"
      response = self.duplo.post(path)
      auth_data = response.json()
      
      # Cache the response
      if "ExpiresAt" not in auth_data:
        # Set default expiration if not provided
        auth_data["ExpiresAt"] = self.duplo.expiration()
      self.duplo.set_cached_item(cache_key, auth_data)
    
    return {
      'headers': {
        'Authorization': f'Bearer {auth_data["Token"]}',
        'duplotoken': self.duplo.token
      },
      'argo_tenant_id': auth_data["TenantId"]
    }


  def _get_argo_path(self, path: str, argo_tenant_id: str) -> str:
    """Get the full Argo API path.
    
    Args:
      path: The API path relative to Argo
      argo_tenant_id: The Argo tenant ID from auth
      
    Returns:
      str: The full path including tenant info
    """
    return f"argo-wf/{argo_tenant_id}/api/v1/{path}?current_tenant_id={self.tenant_id}"


@Resource("argo_wf", scope="tenant")
class DuploArgoWorkflow(ArgoBase):
  """Resource for creating and managing Argo Workflow resources in DuploCloud.

  This resource provides commands to interact with Argo Workflows via the DuploCloud proxy.

  Usage: Basic CLI Use
    ```sh
    duploctl argo_wf <action>
    ```
  """

  @Command()
  def auth(self) -> dict:
    """Get Argo Authentication Info

    Retrieve the Argo Workflow authentication token and admin status for the current tenant.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf auth
      ```

    Returns:
      dict: Authentication info with Token, IsAdmin, TenantId, ExpiresAt.
    """
    cache_key = self.duplo.cache_key_for("argo-auth")
    try:
      return self.duplo.get_cached_item(cache_key)
    except KeyError:
      # Trigger auth to populate cache
      self._get_argo_auth_headers()
      return self.duplo.get_cached_item(cache_key)

  @Command("list_workflows")
  def list(self) -> list:
    """List Workflows

    Retrieve a list of all workflows in the current tenant/namespace.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf list
      ```

    Example: List with JSON output
      ```bash
      duploctl argo_wf list --query "items[*].metadata.name"
      ```

    Returns:
      list: A list of workflows in the tenant.
    """
    auth = self._get_argo_auth_headers()
    path = f"workflows/{self._namespace}"
    full_path = self._get_argo_path(path, auth['argo_tenant_id'])
    return self.duplo.get(full_path, headers=auth['headers'], mergeHeaders=False).json()

  @Command("get", "get_workflow")
  def find(self, name: args.NAME) -> dict:
    """Get Workflow

    Find a specific workflow by name.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf find <workflow-name>
      ```

    Example: Get workflow status
      ```bash
      duploctl argo_wf find my-workflow --query "status.phase"
      ```

    Args:
      name: The name of the workflow.

    Returns:
      dict: The full workflow object.
    """
    auth = self._get_argo_auth_headers()
    path = f"workflows/{self._namespace}/{self.duplo.sanitize_path_segment(name)}"
    full_path = self._get_argo_path(path, auth['argo_tenant_id'])
    return self.duplo.get(full_path, headers=auth['headers'], mergeHeaders=False).json()

  @Command("submit")
  def create(self, body: args.BODY) -> dict:
    """Create Workflow

    Create a new workflow from a workflow specification.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf create --file workflow.yaml
      ```
      Contents of the `workflow.yaml` file
      ```yaml
      --8<-- "src/tests/data/argo_workflow.yaml"
      ```

    Example: Create using -f flag
      ```bash
      duploctl argo_wf create -f workflow.yaml
      ```

    Args:
      body: The workflow specification.

    Returns:
      dict: The created workflow object.
    """
    auth = self._get_argo_auth_headers()
    path = f"workflows/{self._namespace}"
    full_path = self._get_argo_path(path, auth['argo_tenant_id'])
    return self.duplo.post(full_path, data=body, headers=auth['headers'], mergeHeaders=False).json()

  @Command("delete_workflow")
  def delete(self, name: args.NAME) -> dict:
    """Delete Workflow

    Delete a workflow by name.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf delete <workflow-name>
      ```

    Example: Delete a specific workflow
      ```bash
      duploctl argo_wf delete my-workflow-abc123
      ```

    Args:
      name: The name of the workflow to delete.

    Returns:
      dict: Deletion confirmation.
    """
    auth = self._get_argo_auth_headers()
    path = f"workflows/{self._namespace}/{self.duplo.sanitize_path_segment(name)}"
    full_path = self._get_argo_path(path, auth['argo_tenant_id'])
    return self.duplo.delete(full_path, headers=auth['headers'], mergeHeaders=False).json()

  @Command()
  def apply(self, body: args.BODY) -> dict:
    """Apply Workflow

    Create a new workflow if it does not exist. If the workflow already exists,
    an error is raised since Argo Workflows are immutable once created. If metadata.generateName is specified, a new workflow will be created with a random name and the given prefix.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf apply --file workflow.yaml
      ```
      Contents of the `workflow.yaml` file
      ```yaml
      --8<-- "src/tests/data/argo_workflow.yaml"
      ```

    Example: Apply using -f flag
      ```bash
      duploctl argo_wf apply -f workflow.yaml
      ```

    Args:
      body: The workflow specification.

    Returns:
      dict: The created workflow object.

    Raises:
      DuploError: If workflow already exists (workflows are immutable).
    """
    name = body.get("workflow", {}).get("metadata", {}).get("name")
    if name:
      try:
        self.find(name)
        raise DuploError(
          f"Workflow '{name}' already exists. Argo Workflows are immutable once created. "
          "Delete the existing workflow first or use a different name.",
          409
        )
      except DuploError as e:
        if e.code == 409:
          raise
    return self.create(body)


@Resource("argo_wf_template", scope="tenant")
class DuploArgoWorkflowTemplate(ArgoBase):
  """Resource for creating and managing Argo Workflow Templates in DuploCloud.

  This resource provides commands to interact with Argo Workflow Templates via the DuploCloud proxy.

  Usage: Basic CLI Use
    ```sh
    duploctl argo_wf_template <action>
    ```
  """

  @Command()
  def list(self) -> list:
    """List Workflow Templates

    Retrieve a list of all workflow templates in the current tenant/namespace.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf_template list
      ```

    Example: List template names only
      ```bash
      duploctl argo_wf_template list --query "items[*].metadata.name"
      ```

    Returns:
      list: A list of workflow templates in the tenant.
    """
    auth = self._get_argo_auth_headers()
    path = f"workflow-templates/{self._namespace}"
    full_path = self._get_argo_path(path, auth['argo_tenant_id'])
    return self.duplo.get(full_path, headers=auth['headers'], mergeHeaders=False).json()

  @Command()
  def find(self, name: args.NAME) -> dict:
    """Get Workflow Template

    Find a specific workflow template by name.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf_template find <template-name>
      ```

    Example: Get template entrypoint
      ```bash
      duploctl argo_wf_template find my-template --query "spec.entrypoint"
      ```

    Args:
      name: The name of the workflow template.

    Returns:
      dict: The full workflow template object.
    """
    auth = self._get_argo_auth_headers()
    path = f"workflow-templates/{self._namespace}/{self.duplo.sanitize_path_segment(name)}"
    full_path = self._get_argo_path(path, auth['argo_tenant_id'])
    return self.duplo.get(full_path, headers=auth['headers'], mergeHeaders=False).json()

  @Command()
  def create(self, body: args.BODY) -> dict:
    """Create Workflow Template

    Create a new workflow template.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf_template create --file template.yaml
      ```
      Contents of the `template.yaml` file
      ```yaml
      --8<-- "src/tests/data/argo_wf_template.yaml"
      ```

    Example: Create using -f flag
      ```bash
      duploctl argo_wf_template create -f template.yaml
      ```

    Args:
      body: The workflow template specification.

    Returns:
      dict: The created workflow template object.
    """
    auth = self._get_argo_auth_headers()
    path = f"workflow-templates/{self._namespace}"
    full_path = self._get_argo_path(path, auth['argo_tenant_id'])
    return self.duplo.post(full_path, data=body, headers=auth['headers'], mergeHeaders=False).json()

  @Command()
  def delete(self, name: args.NAME) -> dict:
    """Delete Workflow Template

    Delete a workflow template by name.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf_template delete <template-name>
      ```

    Example: Delete a specific template
      ```bash
      duploctl argo_wf_template delete my-hello-world-template
      ```

    Args:
      name: The name of the workflow template to delete.

    Returns:
      dict: Deletion confirmation.
    """
    auth = self._get_argo_auth_headers()
    path = f"workflow-templates/{self._namespace}/{self.duplo.sanitize_path_segment(name)}"
    full_path = self._get_argo_path(path, auth['argo_tenant_id'])
    return self.duplo.delete(full_path, headers=auth['headers'], mergeHeaders=False).json()

  @Command()
  def update(self, body: args.BODY) -> dict:
    """Update Workflow Template

    Update an existing workflow template.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf_template update --file template.yaml
      ```
      Contents of the `template.yaml` file
      ```yaml
      --8<-- "src/tests/data/argo_wf_template.yaml"
      ```

    Example: Update using -f flag
      ```bash
      duploctl argo_wf_template update -f template.yaml
      ```

    Args:
      body: The workflow template specification with name in metadata.

    Returns:
      dict: The updated workflow template object.
    """  
    name = body.get("template", {}).get("metadata", {}).get("name")
    if not name:
      raise DuploError("Template name is required in metadata for update", 400)
    # Fetch current resourceVersion required by Argo API for updates
    current = self.find(name)
    resource_version = current.get("metadata", {}).get("resourceVersion")
    if resource_version:
      body["template"]["metadata"]["resourceVersion"] = resource_version
    auth = self._get_argo_auth_headers()
    path = f"workflow-templates/{self._namespace}/{self.duplo.sanitize_path_segment(name)}"
    full_path = self._get_argo_path(path, auth['argo_tenant_id'])
    return self.duplo.put(full_path, data=body, headers=auth['headers'], mergeHeaders=False).json()

  @Command()
  def apply(self, body: args.BODY) -> dict:
    """Apply Workflow Template

    Create or update a workflow template. If the template exists, it will be updated.
    Otherwise, a new template will be created.

    Usage: Basic CLI Use
      ```bash
      duploctl argo_wf_template apply --file template.yaml
      ```
      Contents of the `template.yaml` file
      ```yaml
      --8<-- "src/tests/data/argo_wf_template.yaml"
      ```

    Example: Apply using -f flag
      ```bash
      duploctl argo_wf_template apply -f template.yaml
      ```

    Example: Apply and verify
      Apply a template and then verify it was created.
      ```bash
      duploctl argo_wf_template apply -f template.yaml
      duploctl argo_wf_template find my-template
      ```

    Args:
      body: The workflow template specification.

    Returns:
      dict: The created or updated workflow template object.
    """
    name = body.get("template", {}).get("metadata", {}).get("name")
    if name:
      try:
        self.find(name)
        return self.update(body)
      except DuploError:
        pass
    return self.create(body)