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
  
  def __call__(self, cmd: str, *args):
    command = self.command(cmd)
    parser = get_parser(command)
    parsed_args = parser.parse_args(args)
    return command(**vars(parsed_args))
  
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
      except DuploError:
        time.sleep(poll)
    else:
      raise DuploError("Timed out waiting", 404)
      
  
class DuploTenantResource(DuploResource):
  def __init__(self, duplo: DuploClient):
    self.duplo = duplo
    self._tenant = None
    self.tenant_svc = duplo.load('tenant')
  @property
  def tenant(self):
    if not self._tenant:
      self._tenant = self.tenant_svc.find(self.duplo.tenant)
    return self._tenant

class DuploTenantResourceV3(DuploResource):
  def __init__(self, duplo: DuploClient, slug: str):
    self.duplo = duplo
    self._tenant = None
    self.tenant_svc = duplo.load('tenant')
    self.slug = slug
  @property
  def tenant(self):
    if not self._tenant:
      self._tenant = self.tenant_svc.find(self.duplo.tenant)
    return self._tenant
  
  @Command()
  def list(self):
    """Retrieve a list of all resources in a tenant."""
    response = self.duplo.get(self.__endpoint())
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
    response = self.duplo.get(self.__endpoint(name))
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
    self.duplo.delete(self.__endpoint(name))
    return {
      "message": f"{self.slug}/{name} deleted"
    }
  
  @Command()
  def create(self, 
             body: args.BODY,
             wait: args.WAIT=False):
    """Create a V3 resource by name.
    
    Args:
      body (str): The resource to create.
    Returns: 
      Success message.
    Raises:
      DuploError: If the resource could not be created.
    """
    name = self.name_from_body(body)
    response = self.duplo.post(self.__endpoint(), body)
    if wait:
      self.wait(lambda: self.find(name))
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
    response = self.duplo.put(self.__endpoint(name), body)
    return response.json()

  def __endpoint(self, name: str=None):
    tenant_id = self.tenant["TenantId"]
    p = f"v3/subscriptions/{tenant_id}/{self.slug}"
    if name:
      p += f"/{name}"
    return p
