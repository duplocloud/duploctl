from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("configmap")
class DuploConfigMap(DuploTenantResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self):
    """Retrieve a list of all configmaps in a tenant."""
    tenant_id = self.tenant["TenantId"]
    response = self.duplo.get(f"v3/subscriptions/{tenant_id}/k8s/configmap")
    return response.json()

  @Command()
  def find(self, 
           name: args.NAME):
    """Find a configmap by name.
    
    Args:
      name (str): The name of the configmap to find.
    Returns: 
      The configmap object.
    Raises:
      DuploError: If the configmap could not be found.
    """
    try:
      return [s for s in self.list() if s["metadata"]["name"] == name][0]
    except IndexError:
      raise DuploError(f"ConfigMap '{name}' not found", 404)

