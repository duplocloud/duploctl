from duplocloud.client import DuploClient  # Importing necessary modules
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Resource

@Resource("job")  # Decorator to define a resource
class DuploJob(DuploTenantResourceV3):
  
  def __init__(self, duplo: DuploClient):  # Constructor method
    super().__init__(duplo, "k8s/job")  # Calling superclass constructor
    
  
