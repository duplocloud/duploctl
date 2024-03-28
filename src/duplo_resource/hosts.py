from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResource
from duplocloud.errors import DuploError, DuploFailedResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("hosts")
class DuploHosts(DuploTenantResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self):
    """Retrieve a list of all hosts in a tenant."""
    tenant_id = self.tenant["TenantId"]
    response = self.duplo.get(f"subscriptions/{tenant_id}/GetNativeHosts")
    return response.json()
  
  @Command()
  def create(self,
             body: args.BODY,
             wait: args.WAIT=False):
    """Create a host."""
    tenant_id = self.tenant["TenantId"]
    res = self.duplo.post(f"subscriptions/{tenant_id}/CreateNativeHost", body)
    def wait_check():
      name = self.name_from_body(body)
      h = self.find(name)
      if h["Status"] != "running":
        if h["Status"] != "pending":
          raise DuploFailedResource(f"Host '{name}' failed to create.")
        raise DuploError(f"Host '{name}' not ready", 404)
    if wait:
      self.wait(wait_check)
    return {
      "message": f"Successfully created host '{body['FriendlyName']}'",
      "id": res.json()
    }
  
  @Command()
  def delete(self,
             name: args.NAME,
             wait: args.WAIT=False):
    """Delete a host."""
    tenant_id = self.tenant["TenantId"]
    host = self.find(name)
    inst_id = host["InstanceId"]
    res = self.duplo.post(f"subscriptions/{tenant_id}/TerminateNativeHost/{inst_id}", host)
    def wait_check():
      h = None 
      try:
        h = self.find(name)
      except DuploError as e:
        if e.code == 404:
          return None # if 404 then it's gone so finish waiting
        else:
          raise DuploFailedResource(f"Host '{name}' failed to delete.")
      if h["Status"] == "shutting-down" or h["Status"] == "running":
        raise DuploError(f"Host '{name}' not terminated", 404)
    if wait:
      self.wait(wait_check, 500)
    return {
      "message": f"Successfully deleted host '{name}'",
      "data": res.json()
    }

  @Command()
  def find(self, 
           name: args.NAME):
    """Find a host by name.
    
    Args:
      name (str): The name of the host to find.
    Returns: 
      The host object.
    Raises:
      DuploError: If the host could not be found.
    """
    try:
        return [s for s in self.list() if s["FriendlyName"] == name][0]
    except IndexError:
      raise DuploError(f"Host '{name}' not found", 404)
    
  def name_from_body(self, body):
    prefix = f"duploservices-{self.duplo.tenant}"
    name =  body["FriendlyName"]
    if not name.startswith(prefix):
      name = f"{prefix}-{name}"
    return name
