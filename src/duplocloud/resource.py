from .client import DuploClient
from .errors import DuploError, DuploFailedResource
from .commander import get_parser
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

