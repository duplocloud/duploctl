from . import args
from .client import DuploClient
from .errors import DuploError, DuploFailedResource, DuploStillWaiting
from .commander import get_parser, extract_args, Command
import math
import time
import requests

class DuploCommand():
  def __init__(self, duplo: DuploClient):
    self.duplo = duplo
  
  def __call__(self, *args):
    pass

class DuploResource():

  def __init__(self, duplo: DuploClient, api_version: str="v1", slug: str=None, prefixed: bool=False):
    self.duplo = duplo
    self.__logger = None
    self.slug = slug
    self.wait_timeout = 200
    self.wait_poll = 10
    self._prefixed = prefixed
    self.api_version = api_version
  
  def __call__(self, cmd: str, *args):
    c = self.command(cmd)
    return c(*args)

  # TODO: something is off and the logs will duplicate if we do this. Plese figure out how to actually create a logger for each resource.
  # @property
  # def logger(self):
  #   if not self.__logger:
  #     self.__logger = self.duplo.logger_for(self.__class__.__name__)
  #   return self.__logger
  
  def command(self, name: str):
    # TODO: Test the aliased_method further before actually releasing this feature. This will be disabled for now.
    # method = aliased_method(self.__class__, name)
    if not (command := getattr(self, name, None)):
      raise DuploError(f"Invalid command: {name}")
    cliargs = extract_args(command)
    parser = get_parser(cliargs)
    def wrapped(*args, **kwargs):
      pargs = vars(parser.parse_args(args))
      pargs.update(kwargs)
      return command(**pargs)
    return wrapped
  
  def wait(self, wait_check: callable, timeout: int=3600, poll: int=10):
    """Wait for Resource
    
    Waits for a the given wait_check callable to complete successfully. If the global wait_timeout is set on the DuploClient, it will override the timeout parameter so that a user can always choose their own timeout for waiting operations. The timeout param for other functions is just a default value for that particular resource operation.
    
    Args:
      wait_check: A callable function to check if the resource is ready.
      timeout: The maximum time to wait in seconds. Default is 3600 seconds (1 hour).
      poll: The polling interval in seconds. Default is 10 seconds.
    """
    timeout = self.duplo.wait_timeout or timeout
    exp = math.ceil(timeout / poll)
    for _ in range(exp):
      try:
        wait_check()
        break
      except DuploFailedResource as e:
        raise e
      except DuploStillWaiting as e:
        self.duplo.logger.info(e)
        time.sleep(poll)
      except KeyboardInterrupt as e:
        raise e
    else:
      raise DuploStillWaiting("Timed out waiting")

class DuploResourceV2(DuploResource):

  def __init__(self, duplo: DuploClient, slug: str = None, prefixed: bool = False):
    super().__init__(duplo, api_version="v2", slug=slug, prefixed=prefixed)

  def name_from_body(self, body):
    return body["Name"]
  
  def endpoint(self, path: str=None):
    """Portal-scoped endpoint for V2 resources.
    
    Returns the path as-is for portal-level resources.
    This will be overridden by tenant-scoped injection if scope="tenant".
    """
    return path
  
  @Command()
  def list(self) -> list:
    """Retrieve a List of {{kind}}
    
    Usage: cli usage
      ```sh
      duploctl {{kind | lower}} list
      ```

    Returns:
      list: A list of {{kind}}.
    """
    response = self.duplo.get(self.endpoint(self.paths["list"]))
    return response.json()
  @Command()
  def find(self, 
           name: args.NAME) -> dict:
    """Find a {{kind}} by name.

    Usage: cli usage
      ```sh
      duploctl {{kind | lower}} find <name>
      ```
    
    Args:
      name: The name of the {{kind}} to find.

    Returns: 
      resource: The {{kind}} object.
      
    Raises:
      DuploError: If the {{kind}} could not be found.
    """
    try:
      return [s for s in self.list() if self.name_from_body(s) == name][0]
    except IndexError:
      raise DuploError(f"{self.kind} '{name}' not found", 404)
      
  @Command()
  def apply(self,
             body: args.BODY,
             wait: args.WAIT = False):
    """Apply a service."""
    name = self.name_from_body(body)
    try:
      self.find(name)
      return self.update(name, body, wait)
    except DuploError:
      return self.create(body, wait)
  

class DuploResourceV3(DuploResource):
  def __init__(self, duplo: DuploClient, slug: str, prefixed: bool = False):
    super().__init__(duplo, api_version="v3", slug=slug, prefixed=prefixed)

  def name_from_body(self, body):
    return body["metadata"]["name"]

  def endpoint(self, name: str=None, path: str=None):
    """Portal-scoped endpoint for V3 resources.
    
    Returns a v3 API path for portal-level resources.
    This will be overridden by tenant-scoped injection if scope="tenant".
    """
    p = f"v3/{self.slug}"
    if name:
      p += f"/{name}"
    if path:
      p += f"/{path}"
    return p
  
  @Command()
  def list(self) -> list:
    """Retrieve a List of {{kind}} resources

    Usage: cli usage
      ```sh
      duploctl {{kind | lower}} list
      ```
    
    Returns:
      list: A list of {{kind}}.
    """
    response = self.duplo.get(self.endpoint())
    return response.json()
  
  @Command()
  def find(self, 
           name: args.NAME) -> dict:
    """Find {{kind}} resources by name.

    Usage: cli usage
      ```sh
      duploctl {{kind | lower}} find <name>
      ```
    
    Args:
      name: The name of the {{kind}} resource to find.

    Returns: 
      resource: The {{kind}} object.
      
    Raises:
      DuploError: If the {{kind}} could not be found.
    """
    n = self.prefixed_name(name) if self._prefixed else name
    response = self.duplo.get(self.endpoint(n))
    return response.json()
  
  @Command()
  def delete(self, 
             name: args.NAME) -> dict:
    """Delete a {{kind}} resource by name.

    Usage: cli usage
      ```sh
      duploctl {{kind | lower}} delete <name>
      ```
    
    Args:
      name: The name of the {{kind}} resource to delete.

    Returns: 
      message: A success message.

    Raises:
      DuploError: If the {{kind}} resource could not be found or deleted. 
    """
    n = self.prefixed_name(name) if self._prefixed else name
    self.duplo.delete(self.endpoint(n))
    return {
      "message": f"{self.slug}/{name} deleted"
    }
  
  @Command()
  def create(self, 
             body: args.BODY,
             wait_check: callable=None) -> dict:
    """Create a {{kind}} resource.

    Usage: CLI Usage
      ```sh
      duploctl {{kind | lower}} create -f '{{kind | lower}}.yaml'
      ```
      Contents of the `{{kind|lower}}.yaml` file
      ```yaml
      --8<-- "src/tests/data/{{kind|lower}}.yaml"
      ```

    Example: One liner example
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/{{kind|lower}}.yaml"
      \"\"\" | duploctl {{kind | lower}} create -f -
      ```
    
    Args:
      body: The resource to create.
      wait: Wait for the resource to be created.
      wait_check: A callable function to check if the resource

    Returns: 
      message: Success message.

    Raises:
      DuploError: If the resource could not be created.
    """
    name = self.name_from_body(body)
    response = self.duplo.post(self.endpoint(), body)
    if self.duplo.wait:
      self.wait(wait_check or (lambda: self.find(name)), self.wait_timeout, self.wait_poll)
    return response.json()
  
  @Command()
  def update(self, 
             name: args.NAME = None,
             body: args.BODY = None,
             patches: args.PATCHES = None,):
    """Update a V3 resource by name.
    
    Args:
      name: The name of the resource to update.
      body: The resource to update.
      patches: The patches to apply to the resource.

    Returns: 
      message: Success message.

    Raises:
      DuploError: If the resource could not be created.
    """
    if not name and not body:
      raise DuploError("Name is required when body is not provided")
    body = body or self.find(name)
    if patches:
      body = self.duplo.jsonpatch(body, patches)
    name = name if name else self.name_from_body(body)
    n = self.prefixed_name(name) if self._prefixed else name
    response = self.duplo.put(self.endpoint(n), body)
    return response.json()
  
  @Command()
  def apply(self,
             body: args.BODY,
             wait: args.WAIT = False,
             patches: args.PATCHES = None,) -> dict:
    """Apply a {{kind}}
    
    Create or Update a {{kind}} resource with Duplocloud cli. 

    Usage: CLI Usage
      ```sh
      duploctl {{kind | lower}} apply -f '{{kind | lower}}.yaml'
      ```
      Contents of the `{{kind|lower}}.yaml` file
      ```yaml
      --8<-- "src/tests/data/{{kind|lower}}.yaml"
      ```
    
    Args:
      body: The resource to apply.
      wait: Wait for the resource to be created.
      patches: The patches to apply to the resource.

    Returns:
      message: Success message.
    """
    name = self.name_from_body(body)
    try:
      self.find(name)
      return self.update(name=name, body=body, patches=patches)
    except DuploError:
      return self.create(body, wait)


class DuploTenantResourceV4(DuploResource):
  """Base class for tenant-scoped resources (V4).
  
  This class provides common tenant-related functionality including:
  - Lazy-loaded tenant and tenant_id properties
  - Dynamic resource prefix from system info (via DuploClient.resource_prefix)
  - Kubernetes namespace generation
  - Infrastructure service access with caching
  
  Extend this class for resources that operate within a tenant context.
  
  Note: Named V4 to follow existing V2/V3 naming convention.
  """

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self._tenant = None
    self._tenant_id = None
    self._infra_config = None
    self.tenant_svc = duplo.load('tenant')
    self.infra_svc = duplo.load('infrastructure')

  @property
  def tenant(self) -> dict:
    if not self._tenant:
      self._tenant = self.tenant_svc.find()
      self._tenant_id = self._tenant["TenantId"]
    return self._tenant

  @property
  def tenant_id(self) -> str:
    if not self._tenant_id:
      if self._tenant:
        self._tenant_id = self._tenant["TenantId"]
      elif self.duplo.tenantid:
        self._tenant_id = self.duplo.tenantid
      else:
        self._tenant_id = self.tenant["TenantId"]
    return self._tenant_id

  @property
  def resource_prefix(self) -> str:
    return self.duplo.resource_prefix

  @property
  def namespace(self) -> str:
    return f"{self.resource_prefix}-{self.tenant['AccountName']}"

  @property
  def prefix(self) -> str:
    return f"{self.namespace}-"

  def prefixed_name(self, name: str) -> str:
    """Add tenant prefix to a resource name if not already present.
    
    Args:
      name: The resource name.
      
    Returns:
      str: The prefixed resource name.
    """
    if not name.startswith(self.prefix):
      name = f"{self.prefix}{name}"
    return name

  def get_infra_config(self, plan_id: str = None) -> dict:
    """Get infrastructure configuration with caching.
    
    Fetches and caches the infrastructure configuration for the tenant's
    plan or a specified plan ID.
    
    Args:
      plan_id: Optional plan ID. If not provided, uses the tenant's PlanID.
      
    Returns:
      dict: The infrastructure configuration.
      
    Raises:
      DuploError: If tenant has no associated infrastructure plan.
    """
    if self._infra_config is None:
      pid = plan_id or self.tenant.get("PlanID")
      if not pid:
        raise DuploError("Tenant has no associated infrastructure plan", 400)
      self._infra_config = self.infra_svc.find(pid)
    return self._infra_config


class DuploProxyResource(DuploTenantResourceV4):
  """Base class for resources that use external APIs through Duplo proxy.
  
  This class extends DuploTenantResourceV4 to support proxy-style APIs where:
  - Authentication may use a different token flow
  - Requests go through Duplo as a proxy to external services
  - Custom headers and URL patterns are needed
  
  Provides:
  - _make_request(): HTTP request wrapper with proper exception handling
  - _is_proxy_auth_expired(): Check if cached auth token is expired
  - _build_proxy_headers(): Standard header construction
  - Response validation via DuploClient.validate_response()
  
  Subclasses should implement:
  - _get_proxy_auth(): Get authentication for the proxy service
  - _proxy_request(): Make requests to the proxied API (use _make_request internally)
  
  Example subclasses: Argo Workflows, future Kubernetes API proxies, etc.
  """

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self._proxy_auth = None

  def _is_proxy_auth_expired(self, expiration_key: str = "ExpiresAt") -> bool:
    """Check if the cached proxy auth token is expired.
    
    Uses DuploClient.expired() for consistent expiration checking.
    Subclasses can override expiration_key if their auth response
    uses a different field name for expiration.
    
    Args:
      expiration_key: Key in _proxy_auth dict containing expiration time.
      
    Returns:
      bool: True if expired or no auth cached, False if still valid.
    """
    if self._proxy_auth is None:
      return True
    exp = self._proxy_auth.get(expiration_key)
    return self.duplo.expired(exp)

  def _get_proxy_auth(self) -> dict:
    """Get authentication for the proxy service.
    
    Override this method to implement custom authentication flows
    for the proxied service. Should check _is_proxy_auth_expired()
    before returning cached auth.
    
    Returns:
      dict: Authentication info (tokens, tenant IDs, etc.)
    """
    raise NotImplementedError("Subclasses must implement _get_proxy_auth")

  def _proxy_request(self, method: str, path: str, data: dict = None) -> dict:
    """Make a request to the proxied API.
    
    Override this method to implement custom request logic for
    the proxied service. Use _make_request internally for consistent
    error handling.
    
    Args:
      method: HTTP method (GET, POST, PUT, DELETE)
      path: API path
      data: Optional request body
      
    Returns:
      dict: JSON response from the proxied API
    """
    raise NotImplementedError("Subclasses must implement _proxy_request")

  def _make_request(self, method: str, url: str, headers: dict, 
                    data: dict = None, service_name: str = "Proxy"):
    """Make an HTTP request with proper exception handling.
    
    Wraps requests.request with the same exception handling pattern
    used in DuploClient (timeout, connection errors). Uses the centralized
    DuploClient.validate_response for consistent error handling.
    
    Args:
      method: HTTP method (GET, POST, PUT, DELETE)
      url: Full URL to request
      headers: Request headers
      data: Optional request body (will be JSON encoded)
      service_name: Name of the service for error messages
      
    Returns:
      response: The validated requests.Response object
      
    Raises:
      DuploError: On timeout, connection error, or HTTP error status
    """
    try:
      response = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=data,
        timeout=self.duplo.timeout
      )
    except requests.exceptions.Timeout as e:
      raise DuploError(f"Request timed out while connecting to {service_name}", 500) from e
    except requests.exceptions.ConnectionError as e:
      raise DuploError(f"Failed to establish connection with {service_name}", 500) from e
    except requests.exceptions.RequestException as e:
      raise DuploError(f"Failed to send request to {service_name}", 500) from e
    
    return self.duplo.validate_response(response, service_name)

  def _build_proxy_headers(self, proxy_token: str, extra_headers: dict = None) -> dict:
    """Build headers for proxy requests.
    
    Creates a base header dict with Content-Type and Authorization,
    then merges any extra headers provided by subclasses.
    
    Args:
      proxy_token: The authentication token for the proxy service
      extra_headers: Optional dict of additional headers to include.
                     Subclasses can pass service-specific headers here
                     (e.g., {'duplotoken': self.duplo.token} for Argo).
      
    Returns:
      dict: Headers for the proxy request
    """
    headers = {
      'Content-Type': 'application/json',
      'Authorization': f'Bearer {proxy_token}'
    }
    if extra_headers:
      headers.update(extra_headers)
    return headers