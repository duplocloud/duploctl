from .client import DuploClient
from .errors import DuploError

class DuploResource():
  
  def __init__(self, duplo: DuploClient):
    self.duplo = duplo
    self.tenant = None
  
  def get_tenant(self):
    if not self.tenant:
      self.tenant_svc = self.duplo.service("tenant")
      self.tenant = self.tenant_svc.find(self.duplo.tenant_name)
    return self.tenant
  
  def exec(self, subcmd, args=[]):
    if not (func := getattr(self, subcmd, None)):
      raise ValueError(f"Invalid subcommand: {subcmd}")
    try:
      res = func(*args)
      # if res is a dict or list, turn it into json
      if isinstance(res, (dict, list)):
        res = self.duplo.json(res)
      return print(res)
    except Exception as e:
      raise DuploError(f"Error executing subcommand: {subcmd}") from e
    
  
