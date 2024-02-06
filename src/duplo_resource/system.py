from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource

@Resource("system")
class DuploSystem(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def info(self):
    """Retrieve all of the system information."""
    response = self.duplo.get("v3/features/system")
    if (data := response.json()):
      return data
    else:
      raise DuploError("Failed to get system information. Please connect to Adminatrator.", 404)
  