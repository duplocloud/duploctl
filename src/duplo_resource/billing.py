from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource

@Resource("billing")
class DuploBilling(DuploResource):
  
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

  

