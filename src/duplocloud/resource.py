from . import args
from .client import DuploClient
from .errors import DuploError, DuploFailedResource, DuploStillWaiting
from .commander import get_parser, extract_args, Command
import math
import time

class DuploCommand():
  def __init__(self, duplo: DuploClient):
    self.duplo = duplo
  
  def __call__(self, *args):
    pass

class DuploResource():

  def __init__(self, duplo: DuploClient):
    self.duplo = duplo
    self.__logger = None
  
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
    def wrapped(*args):
      pargs = vars(parser.parse_args(args))
      return command(**pargs)
    return wrapped
  
  def wait(self, wait_check: callable, timeout: int=3600, poll: int=10):
    exp = math.ceil(timeout / poll)
    for _ in range(exp):
      try:
        wait_check()
        break
      except DuploFailedResource as e:
        raise e
      except DuploStillWaiting as e:
        if e.message:
          self.duplo.logger.debug(e)
        time.sleep(poll)
      except KeyboardInterrupt as e:
        raise e
    else:
      raise DuploStillWaiting("Timed out waiting")

class DuploResourceV2(DuploResource):

  def name_from_body(self, body):
    return body["Name"]
  def endpoint(self, path: str=None):
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
  
class DuploTenantResourceV2(DuploResourceV2):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self._tenant = None
    self._tenant_id = None
    self.tenant_svc = duplo.load('tenant')
  @property
  def tenant(self):
    if not self._tenant:
      self._tenant = self.tenant_svc.find()
      self._tenant_id = self._tenant["TenantId"]
    return self._tenant
  
  @property
  def tenant_id(self):
    if not self._tenant_id:
      if self._tenant:
        self._tenant_id = self._tenant["TenantId"]
      elif self.duplo.tenantid:
        self._tenant_id = self.duplo.tenantid
      else:
        self._tenant_id = self.tenant["TenantId"]
    return self._tenant_id
  
  def prefixed_name(self, name: str) -> str:
    tenant_name = self.tenant["AccountName"]
    prefix = f"duploservices-{tenant_name}-"
    if not name.startswith(prefix):
      name = f"{prefix}{name}"
    return name
  
  def endpoint(self, path: str=None):
    return f"subscriptions/{self.tenant_id}/{path}"
  

class DuploTenantResourceV3(DuploResource):
  def __init__(self, duplo: DuploClient, slug: str, prefixed: bool = False):
    super().__init__(duplo)
    self._prefixed = prefixed
    self._tenant = None
    self._tenant_id = None
    self.tenant_svc = duplo.load('tenant')
    self.slug = slug
    self.wait_timeout = 200
    self.wait_poll = 10
  @property
  def tenant(self):
    if not self._tenant:
      self._tenant = self.tenant_svc.find()
      self._tenant_id = self._tenant["TenantId"]
    return self._tenant
  
  @property
  def tenant_id(self):
    if not self._tenant_id:
      if self._tenant:
        self._tenant_id = self._tenant["TenantId"]
      elif self.duplo.tenantid:
        self._tenant_id = self.duplo.tenantid
      else:
        self._tenant_id = self.tenant["TenantId"]
    return self._tenant_id
  
  @property
  def prefix(self):
    return f"duploservices-{self.tenant['AccountName']}-"
  
  def prefixed_name(self, name: str) -> str:
    if not name.startswith(self.prefix):
      name = f"{self.prefix}{name}"
    return name
  
  def name_from_body(self, body):
    return body["metadata"]["name"]

  def endpoint(self, name: str=None, path: str=None):
    p = f"v3/subscriptions/{self.tenant_id}/{self.slug}"
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
  
  
  