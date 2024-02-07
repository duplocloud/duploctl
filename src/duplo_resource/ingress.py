from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("ingress")
class DuploIngress(DuploTenantResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self):
    """Retrieve a list of all ingress in a tenant."""
    tenant_id = self.tenant["TenantId"]
    response = self.duplo.get(f"v3/subscriptions/{tenant_id}/k8s/ingress")
    return response.json()
  
  @Command()
  def find(self, 
           name: args.NAME):
    """Find a ingress by name.
    
    Args:
      name (str): The name of the ingress to find.
    Returns: 
      The ingress object.
    Raises:
      DuploError: If the ingress could not be found.
    """
    try:
      return [s for s in self.list() if s["name"] == name][0]
    except IndexError:
      raise DuploError(f"Ingress '{name}' not found", 404)

