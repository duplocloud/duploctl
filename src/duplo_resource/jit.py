from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
@Resource("jit")
class DuploJit(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    
  @Command()
  def aws(self):
    """Retrieve aws session credentials for current user."""
    sts = self.duplo.get("adminproxy/GetJITAwsConsoleAccessUrl")
    return sts.json()
