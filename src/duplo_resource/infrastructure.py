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
