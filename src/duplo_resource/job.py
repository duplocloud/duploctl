from duplocloud.client import DuploClient  # Importing necessary modules
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("job")  # Decorator to define a resource
class DuploJob(DuploTenantResourceV3):
  
  def __init__(self, duplo: DuploClient):  # Constructor method
    super().__init__(duplo, "k8s/job")  # Calling superclass constructor

  @Command()
  def pods(self, 
           name: args.NAME):
    """Get the pods for a service.
    
    Args:
      name (str): The name of the service to get pods for.
    Returns: 
      A list of pods for the service.
    Raises:
      DuploError: If the service could not be found.
    """
    response = self.duplo.get(self.endpoint("GetPods"))
    return [
      pod for pod in response.json() 
      if pod["Name"] == name and pod["ControlledBy"]["QualifiedType"] == "kubernetes:batch/v1/Job"
    ]
  
  @Command()
  def logs(self,
           name: args.NAME,
           watch: args.WAIT = False):
    """Get the logs for a service."""
    pod = self.pods(name)[0]
    data = {
      "HostName": pod["Host"],
      "DockerId": pod["Containers"][0]["DockerId"],
      "Tail": 50
    }
    response = self.duplo.post(self.endpoint("findContainerLogs"), data)
    o = response.json()
    lines = o["Data"].split("\n")
    if lines[-1] == "":
      lines.pop()   
    for l in lines:
      self.duplo.logger.info(l)
    return None
