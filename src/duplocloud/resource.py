from . import args
from .client import DuploClient
from .errors import DuploError, DuploFailedResource
from .commander import get_parser, Command
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
    command = self.command(cmd)
    parser = get_parser(command)
    parsed_args = parser.parse_args(args)
    return command(**vars(parsed_args))

  # something is off and the logs will duplicate if we do this  
  # @property
  # def logger(self):
  #   if not self.__logger:
  #     self.__logger = self.duplo.logger_for(self.__class__.__name__)
  #   return self.__logger
  
  def command(self, name: str):
    if not (command := getattr(self, name, None)):
      raise DuploError(f"Invalid command: {name}")
    return command
  
  def wait(self, wait_check: callable, timeout: int=None, poll: int=10):
    timeout = timeout or self.duplo.timeout
    exp = math.ceil(timeout / poll)
    for _ in range(exp):
      try:
        wait_check()
        break
      except DuploFailedResource as e:

        raise e
      except DuploError as e:
        if e.message:
          self.duplo.logger.info(e)
        time.sleep(poll)
      except KeyboardInterrupt as e:
        raise e
    else:
      raise DuploError("Timed out waiting", 404)
    
class DuploResourceV2(DuploResource):

  def name_from_body(self, body):
    return body["Name"]
  def endpoint(self, path: str=None):
    return path
  @Command()
  def list(self):
    """Retrieve a list of all services in a tenant."""
    response = self.duplo.get(self.endpoint(self.paths["list"]))
    return response.json()
  @Command()
  def find(self, 
           name: args.NAME):
    """Find a resource by name.
    
    Args:
      name (str): The name of the resource to find.
    Returns: 
      The resource object.
    Raises:
      DuploError: If the resource could not be found.
    """
    try:
      return [s for s in self.list() if self.name_from_body(s) == name][0]
    except IndexError:
      raise DuploError(f"{self.kind} '{name}' not found", 404)
      
  
class DuploTenantResourceV2(DuploResourceV2):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self.__tenant = None
    self.tenant_svc = duplo.load('tenant')
  @property
  def tenant(self):
    if not self.__tenant:
      self.__tenant = self.tenant_svc.find(self.duplo.tenant)
    return self.__tenant
  
  def endpoint(self, path: str=None):
    tenant_id = self.tenant["TenantId"]
    p = f"subscriptions/{tenant_id}/{path}"
    return p
  

class DuploTenantResourceV3(DuploResource):
  def __init__(self, duplo: DuploClient, slug: str):
    super().__init__(duplo)
    self.__tenant = None
    self.tenant_svc = duplo.load('tenant')
    self.slug = slug
    self.wait_timeout = 200
    self.wait_poll = 10
  @property
  def tenant(self):
    if not self.__tenant:
      self.__tenant = self.tenant_svc.find(self.duplo.tenant)
    return self.__tenant
  
  @Command()
  def list(self):
    """Retrieve a list of all resources in a tenant."""
    response = self.duplo.get(self.endpoint())
    return response.json()
  
  @Command()
  def find(self, 
           name: args.NAME):
    """Find a V3 resource by name.
    
    Args:
      name (str): The name of the resource to find.
    Returns: 
      The resource.
    Raises:
      DuploError: If the resource could not be found.
    """
    response = self.duplo.get(self.endpoint(name))
    return response.json()
  
  @Command()
  def delete(self, 
             name: args.NAME):
    """Delete a V3 resource by name.
    
    Args:
      name (str): The name of the resource to delete.
    Returns: 
      A success message.
    Raises:
      DuploError: If the resource could not be found or deleted. 
    """
    self.duplo.delete(self.endpoint(name))
    return {
      "message": f"{self.slug}/{name} deleted"
    }
  
  @Command()
  def create(self, 
             body: args.BODY,
             wait: args.WAIT=False,
             wait_check: callable=None):
    """Create a V3 resource by name.
    
    Args:
      body (str): The resource to create.
    Returns: 
      Success message.
    Raises:
      DuploError: If the resource could not be created.
    """
    name = self.name_from_body(body)
    response = self.duplo.post(self.endpoint(), body)
    if wait:
      self.wait(wait_check or (lambda: self.find(name)), self.wait_timeout, self.wait_poll)
    return response.json()
  
  @Command()
  def update(self, 
             body: args.BODY):
    """Update a V3 resource by name.
    
    Args:
      body (str): The resource to update.
    Returns: 
      Success message.
    Raises:
      DuploError: If the resource could not be created.
    """
    name = self.name_from_body(body)
    response = self.duplo.put(self.endpoint(name), body)
    return response.json()
  
  def name_from_body(self, body):
    return body["metadata"]["name"]

  def endpoint(self, name: str=None, path: str=None):
    tenant_id = self.tenant["TenantId"]
    p = f"v3/subscriptions/{tenant_id}/{self.slug}"
    if name:
      p += f"/{name}"
    if path:
      p += f"/{path}"
    return p
