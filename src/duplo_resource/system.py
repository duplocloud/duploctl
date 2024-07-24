from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource

@Resource("system")
class DuploSystem(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def info(self) -> dict:
    """Get system information
    
    Usage: CLI Usage
      ```sh
      duploctl system info
      ```
    """
    return self.duplo.get("v3/features/system").json()
  
  @Command()
  def billing(self) -> dict:
    """Account
    
    Get the account spend for the portal. 

    Usage: CLI Usage
      ```sh
      duploctl system billing
      ```
    """
    response = self.duplo.get("v3/billing/admin/aws/billing")
    return response.json()
