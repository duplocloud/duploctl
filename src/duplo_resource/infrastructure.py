from duplocloud.client import DuploClient
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
    response = self.duplo.get(f"adminproxy/GetInfrastructureConfigs/{name}")
    return response.json()
  
  @Command()
  def create(self, 
             body: args.BODY):
    """Create a new infrastructure."""
    self.duplo.post("adminproxy/CreateInfrastructureConfig", body)
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
