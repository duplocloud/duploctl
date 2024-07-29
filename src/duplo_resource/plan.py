from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("plan")
class DuploPlan(DuploResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self) -> list:
    """List of Plans
    
    Usage: CLI Usage
      ```bash
      duploctl plan list
      ```
    
    Returns:
      list: List of Plans
    """
    response = self.duplo.get("adminproxy/GetPlans")
    return response.json()
  
  @Command()
  def find(self, 
           name: args.NAME) -> dict:
    """Find a Plan by name

    Usage: CLI Usage
      ```bash
      duploctl plan find <name>
      ```
    
    Args:
      name: Plan Name

    Returns:
      dict: Plan Details
    """
    try:
      return [s for s in self.list() if self.name_from_body(s) == name][0]
    except IndexError:
      raise DuploError(f"Plan '{name}' not found", 404)

  def name_from_body(self, body):
    return body["Name"]
