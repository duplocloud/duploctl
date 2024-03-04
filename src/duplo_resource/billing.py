from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("configmap")
class DuploBilling(DuploTenantResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def spend(self):
    """Spend
    
    Get the spend for the tenant. 
    """
    tenant_id = self.tenant["TenantId"]
    response = self.duplo.get(f"v3/billing/subscriptions/{tenant_id}/aws/billing")
    return response.json()

  

