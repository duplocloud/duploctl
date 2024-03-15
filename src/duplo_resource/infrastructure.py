from duplocloud.client import DuploClient
from duplocloud.errors import DuploError, DuploFailedResource
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("infrastructure")
class DuploInfrastructure(DuploResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)

  @Command()
  def eks_config(self,
                 planId: args.PLAN = None):
    """Retrieve eks session credentials for current user."""
    res = self.duplo.get(f"v3/admin/plans/{planId}/k8sClusterConfig")
    return res.json()
  
  @Command()
  def list(self):
    """Retrieve a list of all infrastructures in the Duplo system."""
    response = self.duplo.get("adminproxy/GetInfrastructureConfigs/true")
    return response.json()
  
  @Command()
  def find(self, 
           name: args.NAME):
    """Find an infrastructure by name."""
    response = self.duplo.get(f"adminproxy/GetInfrastructureConfig/{name}")
    return response.json()
  
  @Command()
  def create(self, 
             body: args.BODY,
             wait: args.WAIT=False):
    """Create a new infrastructure."""
    def wait_check():
      i = self.find(body["Name"])
      if i["ProvisioningStatus"] != "Complete":
        # stop waiting if the status contains failed
        if "Failed" in i["ProvisioningStatus"]:
          raise DuploFailedResource(f"Infrastructure '{body['Name']}'")
        raise DuploError(f"Infrastructure '{body['Name']}' not ready", 404)
    self.duplo.post("adminproxy/CreateInfrastructureConfig", body)
    if wait:
      self.wait(wait_check, 1800, 20)
    return {
      "message": f"Infrastructure '{body['Name']}' created"
    }
  
  @Command()
  def delete(self,
             name: args.NAME):
    """Delete an infrastructure."""
    self.duplo.post(f"adminproxy/DeleteInfrastructureConfig/{name}", None)
    return {
      "message": f"Infrastructure '{name}' deleted"
    }

