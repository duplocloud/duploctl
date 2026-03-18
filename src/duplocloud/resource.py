from . import args
from .controller import DuploCtl
from .errors import DuploError, DuploFailedResource, DuploNotFound, DuploStillWaiting, DuploConnectionError
from .commander import get_parser, extract_args, get_command_schema, Command
import math
import time

class DuploCommand():
  def __init__(self, duplo: DuploCtl):
    self.duplo = duplo
  
  def __call__(self, *args):
    pass

class DuploResource():

  def __init__(self, duplo: DuploCtl, api_version: str="v1", slug: str=None, prefixed: bool=False):
    self.duplo = duplo
    self.__logger = None
    self.slug = slug
    self.wait_timeout = 200
    self.wait_poll = 10
    self._prefixed = prefixed
    self.api_version = api_version
  
  def __call__(self, cmd: str, *args, **kwargs):
    c = self.command(cmd)
    return c(*args, **kwargs)

  # TODO: something is off and the logs will duplicate if we do this. Plese figure out how to actually create a logger for each resource.
  # @property
  # def logger(self):
  #   if not self.__logger:
  #     self.__logger = self.duplo.logger_for(self.__class__.__name__)
  #   return self.__logger
  
  def command(self, name: str):
    cmd = get_command_schema(self.__class__, name)
    command = getattr(self, cmd["method"])
    cliargs = extract_args(command)
    parser = get_parser(cliargs)
    # only get the model name if we have validation turned on
    model = self.duplo.load_model(cmd.get("model")) if self.duplo.validate else None
    def wrapped(*args, **kwargs):
      pargs = vars(parser.parse_args(args))
      pargs.update(kwargs)
      # if validation was enabled then the body will be validated
      if model and "body" in pargs and pargs["body"] is not None:
        pargs["body"] = self.duplo.validate_model(model, pargs["body"])
      return command(**pargs)
    return wrapped
  
  def wait(self, wait_check: callable, timeout: int=3600, poll: int=10):
    """Wait for Resource

    Waits for a the given wait_check callable to complete successfully. If the global wait_timeout is set on the DuploCtl, it will override the timeout parameter so that a user can always choose their own timeout for waiting operations. The timeout param for other functions is just a default value for that particular resource operation.

    The GET cache is disabled for the duration of the wait so that each
    poll reflects the live API state rather than a stale cached response.

    Args:
      wait_check: A callable function to check if the resource is ready.
      timeout: The maximum time to wait in seconds. Default is 3600 seconds (1 hour).
      poll: The polling interval in seconds. Default is 10 seconds.
    """
    self.client.disable_get_cache()
    timeout = self.duplo.wait_timeout or timeout
    exp = math.ceil(timeout / poll)
    max_connection_errors = 10
    connection_error_count = 0
    for _ in range(exp):
      try:
        wait_check()
        break
      except DuploFailedResource as e:
        raise e
      except DuploStillWaiting as e:
        self.duplo.logger.info(e)
        connection_error_count = 0
        time.sleep(poll)
      except DuploConnectionError as e:
        connection_error_count += 1
        if connection_error_count >= max_connection_errors:
          raise DuploFailedResource(f"Connection to Duplo (failed after {connection_error_count} retries)") from e
        self.duplo.logger.warning(f"Transient connection error during wait, retrying: {e}")
        time.sleep(poll)
      except KeyboardInterrupt as e:
        raise e
    else:
      raise DuploStillWaiting("Timed out waiting")

class DuploResourceV2(DuploResource):

  def __init__(self, duplo: DuploCtl, slug: str = None, prefixed: bool = False):
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
    response = self.client.get(self.endpoint(self.paths["list"]))
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
      raise DuploNotFound(name, self.kind)
      
  @Command()
  def apply(self,
             body: args.BODY,
             wait: args.WAIT = False):
    """Apply a service."""
    name = self.name_from_body(body)
    try:
      self.find(name)
      return self.update(name, body)
    except DuploNotFound:
      return self.create(body)
  

class DuploResourceV3(DuploResource):
  def __init__(self, duplo: DuploCtl, slug: str, prefixed: bool = False):
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
    response = self.client.get(self.endpoint())
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
    response = self.client.get(self.endpoint(n))
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
    self.client.delete(self.endpoint(n))
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
    response = self.client.post(self.endpoint(), body)
    if self.duplo.wait:
      def _default_wait_check():
        try:
          self.find(name)
        except DuploError:
          raise DuploStillWaiting(f"Waiting for resource '{name}' to become available")
      self.wait(wait_check or _default_wait_check, self.wait_timeout, self.wait_poll)
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
    response = self.client.put(self.endpoint(n), body)
    return response.json()
  
  @Command()
  def apply(self,
             body: args.BODY,
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
    except DuploNotFound:
      return self.create(body)


