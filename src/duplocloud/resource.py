from .client import DuploClient
from .errors import DuploError
from .commander import get_parser

class DuploResource():
  
  def __init__(self, duplo: DuploClient):
    self.duplo = duplo
    self.tenant = None
  
  def command(self, name):
    if not (command := getattr(self, name, None)):
      raise DuploError(f"Invalid command: {name}")
    return command
  
  def exec(self, cmd, args=[]):
    command = self.command(cmd)
    parser = get_parser(command)
    parsed_args = parser.parse_args(args)
    return command(**vars(parsed_args))
  
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

