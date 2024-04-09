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
    self.duplo.disable_get_cache()

  @Command()  
  def create(self, 
             body: args.BODY, 
             wait: args.WAIT = False):
    """Create a job."""
    name = self.name_from_body(body)
    log_count = {}
    a = 0
    s = 0
    f = 0
    def show_new_logs():
      
      logs = self.logs(name)
      # self.duplo.logger.info(f"Logs: {len(logs)}")
      for pod, lines in logs.items():
        last = log_count.get(pod, 0)
        count = len(lines)
        diff = count - last
        log_count[pod] = count
        # self.duplo.logger.info(f"last {last} count {count} diff {diff}")
        if diff > 0:
          for line in lines[-diff:]:
            self.duplo.logger.info(f"{pod}: {line}")
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
      # self.duplo.logger.info(f"There are {len(pods)} pods")
      show_new_logs()
      if len(fail) > 0:
        raise DuploFailedResource(f"Job {name} failed with {fail[0]['reason']}: {fail[0]['message']}")
      if not len(cpl) > 0:
        raise DuploError(None)
    return super().create(body, wait, wait_check)


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
    tenant_id = self.tenant["TenantId"]
    response = self.duplo.get(f"subscriptions/{tenant_id}/GetPods")
    return [
      pod for pod in response.json() 
      if pod["Name"] == name and pod["ControlledBy"]["QualifiedType"] == "kubernetes:batch/v1/Job"
    ]
  
  @Command()
  def logs(self,
           name: args.NAME,
           wait: args.WAIT = False):
    """Get the logs for a service."""
    tenant_id = self.tenant["TenantId"]
    pods = self.pods(name)
    def pod_logs(pod):
      data = {
        "HostName": pod["Host"],
        "DockerId": pod["Containers"][0]["DockerId"],
        "Tail": 50
      }
      response = self.duplo.post(f"subscriptions/{tenant_id}/findContainerLogs", data)
      o = response.json()
      lines = o["Data"].split("\n")
      if lines[-1] == "":
        lines.pop()   
      return lines
    logs = {pod["InstanceId"]: pod_logs(pod) for pod in pods if pod["CurrentStatus"] in [1, 11, 7]} 
    return logs
