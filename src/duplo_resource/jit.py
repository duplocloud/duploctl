from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.errors import DuploError

class DuploJit(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    # self.tenent_svc = duplo.service('tenant')
    
  def session(self):
    """Retrieve a list of all users in the Duplo system."""
    return self.duplo.get("adminproxy/GetJITAwsConsoleAccessUrl")
