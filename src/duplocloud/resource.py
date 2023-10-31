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
    res = command(**vars(parsed_args))
    # if res is a dict or list, turn it into json
    if isinstance(res, (dict, list)):
      res = self.duplo.json(res)
    return print(res)
    
class DuploTenantResource(DuploResource):
  def __init__(self, duplo: DuploClient):
    self.duplo = duplo
    self.tenant = None
    self.tenant_svc = duplo.load('tenant')
  def get_tenant(self):
    if not self.tenant:
      self.tenant = self.tenant_svc.find(self.duplo.tenant)
    return self.tenant
