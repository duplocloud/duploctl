from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResource
from duplocloud.errors import DuploError
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
