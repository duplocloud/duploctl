from duplocloud.controller import DuploCtl
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource

@Resource("system")
class DuploSystem(DuploResource):
  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)
  
  @Command()
  def info(self) -> dict:
    """Get system information
    
    Usage: CLI Usage
      ```sh
      duploctl system info
      ```
    """
    return self.client.get("v3/features/system").json()
  
  @Command()
  def billing(self) -> dict:
    """Account
    
    Get the account spend for the portal. 

    Usage: CLI Usage
      ```sh
      duploctl system billing
      ```
    """
    response = self.client.get("v3/billing/admin/aws/billing")
    return response.json()
