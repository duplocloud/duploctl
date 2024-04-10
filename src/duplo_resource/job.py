from duplocloud.client import DuploClient  # Importing necessary modules
from duplocloud.errors import DuploError, DuploFailedResource
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("job")  # Decorator to define a resource
class DuploJob(DuploTenantResourceV3):
  
  def __init__(self, duplo: DuploClient):  # Constructor method
    super().__init__(duplo, "k8s/job")  
    self.wait_timeout = 1000
    self.wait_poll = 3
    self.__pod_svc = self.duplo.load("pod")

  @Command()  
  def create(self, 
             body: args.BODY, 
             wait: args.WAIT = False):
    """Create a job."""
    name = self.name_from_body(body)
    a = 0
    s = 0
    f = 0
    def wait_check():
      nonlocal a, s, f
      job = self.find(name)
      active = job["status"].get("active", 0)
      succeeded = job["status"].get("succeeded", 0)
      failed = job["status"].get("failed", 0)
      completions = job["spec"].get("completions", 1)
      limit = job["spec"].get("backoffLimit", 6)
      cond = job["status"].get("conditions", [])
      cpl = [c for c in cond if c["type"] == "Complete" and c["status"] == "True"]
      fail = [c for c in cond if c["type"] == "Failed" and c["status"] == "True"]
      if (a != active or s != succeeded or f != failed):
        a = active
        s = succeeded
        f = failed
        self.duplo.logger.info(f"Job {name}: active({active}/{completions}), succeeded({succeeded}/{completions}), failed({failed}/{limit})")
      # make sure we can get pods and logs first
      pods_exist = (active > 0 or succeeded > 0 or failed > 0)
      pods = self.pods(name)
      if pods_exist and len(pods) == 0:
        raise DuploError(None)
      # display the logs
      for pod in pods:
        self.__pod_svc.logs(pod=pod)
      # make sure we got all of the logs
      pod_count = active + succeeded + failed
      if len(pods) != pod_count:
        raise DuploError(None)
      if len(fail) > 0:
        raise DuploFailedResource(f"Job {name} failed with {fail[0]['reason']}: {fail[0]['message']}")
      if not len(cpl) > 0:
        raise DuploError(None)
    super().create(body, wait, wait_check)
    return {
      "message": f"Job {name} ran successfully."
    }


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
    pods = self.__pod_svc.list()
    return [
      pod for pod in pods
      if pod["Name"] == name and pod["ControlledBy"]["QualifiedType"] == "kubernetes:batch/v1/Job"
    ]
