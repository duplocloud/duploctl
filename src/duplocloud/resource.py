from .client import DuploClient
from .errors import DuploError
from .commander import exec

class DuploResource():
  
  def __init__(self, duplo: DuploClient):
    self.duplo = duplo
    self.tenant = None
  
  def get_tenant(self):
    if not self.tenant:
      self.tenant_svc = self.duplo.service("tenant")
      self.tenant = self.tenant_svc.find(self.duplo.tenant_name)
    return self.tenant
  
  def command(self, name):
    if not (cmd := getattr(self, name, None)):
      raise DuploError(f"Invalid subcommand: {name}")
    return cmd
  
  def exec(self, subcmd, args=[]):
    try:
      cmd = self.command(subcmd)
      res = exec(cmd, args)
      # if res is a dict or list, turn it into json
      if isinstance(res, (dict, list)):
        res = self.duplo.json(res)
      return print(res)
    except DuploError as e:
      raise e
    except Exception as e:
      raise DuploError(f"Error executing subcommand: {subcmd}") from e
    
  
