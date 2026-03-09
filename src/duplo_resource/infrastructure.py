from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploFailedResource, DuploStillWaiting
from duplocloud.resource import DuploResourceV2
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("infrastructure")
class DuploInfrastructure(DuploResourceV2):
  
  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)

  @Command()
  def eks_config(self,
                 planId: args.PLAN = None):
    """Retrieve eks session credentials for current user."""
    res = self.client.get(f"v3/admin/plans/{planId}/k8sClusterConfig")
    return res.json()
  
  @Command()
  def list(self):
    """Retrieve a list of all infrastructures in the Duplo system."""
    response = self.client.get("adminproxy/GetInfrastructureConfigs/true")
    return response.json()
  
  @Command()
  def find(self, 
           name: args.NAME):
    """Find an infrastructure by name."""
    response = self.client.get(f"adminproxy/GetInfrastructureConfig/{name}")
    return response.json()
  
  _INFRA_FAULT_TENANTS = {"System.VPC", "System.AwsInfrastructure"}

  def _faults_for(self, name: str) -> list:
    """Return faults relevant to the named infrastructure.

    Includes faults where Resource.Name matches the infra name directly,
    plus generic system-level faults from infrastructure-related modules
    (System.VPC, System.AwsInfrastructure) that have no specific resource name.
    """
    try:
      all_faults = self.faults(name)
    except Exception:
      return []
    return [
      f for f in all_faults
      if f.get("Resource", {}).get("Name") == name
      or (
        f.get("TenantId") in self._INFRA_FAULT_TENANTS
        and f.get("Resource", {}).get("Name") == "Generic"
      )
    ]

  @Command()
  def create(self,
             body: args.BODY):
    """Create a new infrastructure."""
    status = None
    name = body["Name"]
    def wait_check():
      nonlocal status
      i = self.find(name)
      s = i.get("ProvisioningStatus", "submitted")
      if status != s:
        self.duplo.logger.warning(f"Infrastructure '{name}' - {s}")
        status = s
      if s != "Complete":
        # stop waiting if the status contains failed
        if "Failed" in s:
          fault_descs = [
            f.get("Description", "")
            for f in self._faults_for(name)
            if f.get("Description")
          ]
          detail = (" | Faults: " + "; ".join(fault_descs)) if fault_descs else ""
          raise DuploFailedResource(f"Infrastructure '{name}' - {s}{detail}")
        raise DuploStillWaiting(f"Infrastructure '{name}' is waiting for status Complete")
    self.client.post("adminproxy/CreateInfrastructureConfig", body)
    if self.duplo.wait:
      self.wait(wait_check, 1800, 20)
    return {
      "message": f"Infrastructure '{body['Name']}' created"
    }
  
  @Command()
  def delete(self,
             name: args.NAME):
    """Delete an infrastructure."""
    self.client.post(f"adminproxy/DeleteInfrastructureConfig/{name}", None)
    return {
      "message": f"Infrastructure '{name}' deleted"
    }

  @Command()
  def faults(self, 
             name: args.NAME):
    """Retrieve a list of all infrastructure faults in the Duplo system."""
    response = self.client.get("adminproxy/GetAllFaults")
    faults = response.json()
    response = self.client.get("admin/GetAllFaults")
    faults += response.json()
    return faults
