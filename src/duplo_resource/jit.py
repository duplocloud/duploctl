from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("jit")
class DuploJit(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    
  @Command()
  def aws(self):
    """Retrieve a list of all users in the Duplo system."""
    sts = self.duplo.get("adminproxy/GetJITAwsConsoleAccessUrl")
    return sts
