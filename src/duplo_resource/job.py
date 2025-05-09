from duplocloud.client import DuploClient  # Importing necessary modules
from duplocloud.errors import DuploFailedResource, DuploStillWaiting
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("job")  # Decorator to define a resource
class DuploJob(DuploTenantResourceV3):
  """Manage Duplo Kubernetes Jobs

  Duplo Jobs provide a way to run containerized tasks to completion in a Kubernetes cluster.

  See more details at: https://docs.duplocloud.com/docs/kubernetes-overview/jobs
  """
  def __init__(self, duplo: DuploClient):  # Constructor method
    super().__init__(duplo, "k8s/job")  
    self.wait_timeout = 1000
    self.wait_poll = 3
    self.__pod_svc = self.duplo.load("pod")

  @Command()  
  def create(self, 
             body: args.BODY):
    """Create a Kubernetes Job.

    Creates a new Job with the specified configuration. The Job will create pods
    and ensure they complete successfully according to the completion criteria.

    Usage: CLI Usage
      ```sh
      duploctl job create -f job.yaml
      ```
      Contents of the `job.yaml` file
      ```yaml
      --8<-- "src/tests/data/job.yaml"
      ```
    
    Example: Create a Job using a one-liner.
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/job.yaml"
      \"\"\" | duploctl job create -f -
      ```

    Example: Create a Job using a file.
      ```sh
      duploctl job create -f job.yaml
      ```

    Args:
      body: The complete Job configuration including container specs, completions,
            and other parameters.

    Returns:
      message: Success message confirming the Job creation.

    Raises:
      DuploError: If the Job could not be created due to invalid configuration.
      DuploFailedResource: If the Job's pods encounter faults during execution.
    """
    name = self.name_from_body(body)
    a = 0
    s = 0
    f = 0
    def check_pod_faults(pod, faults):
      fs = [f for f in faults if f["Resource"].get("Name", None) == pod["InstanceId"]]
      fsct = len(fs)
      if fsct > 0:
        d = "\n".join([f["Description"] for f in fs])
        raise DuploFailedResource(f"Pod {pod['InstanceId']} raised {fsct} faults.\n{d}")
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
        self.duplo.logger.warn(f"Job {name}: active({active}/{completions}), succeeded({succeeded}/{completions}), failed({failed}/{limit})")
      # make sure we can get pods and logs first
      pods_exist = (active > 0 or succeeded > 0 or failed > 0)
      pods = self.pods(name)
      podct = len(pods)
      if pods_exist and podct == 0:
        raise DuploStillWaiting(f"Job {name} has no pods {pods_exist} {podct}")
      # check for any faults and show the logs if we can
      faults = self.tenant_svc.faults(id=self.tenant_id)
      for pod in pods:
        check_pod_faults(pod, faults)
        self.__pod_svc.logs(pod=pod)
      # make sure we got all of the logs
      pod_count = active + succeeded + failed
      if podct != pod_count:
        raise DuploStillWaiting(f"Expected {pod_count} pods, got {podct}")
      if len(fail) > 0:
        raise DuploFailedResource(f"Job {name} failed with {fail[0]['reason']}: {fail[0]['message']}")
      
      # if none have completed, keep waiting
      if not len(cpl) > 0:
        raise DuploStillWaiting(f"Job '{name}' is waiting for 'Complete' condition")
    super().create(body, wait_check)
    return {
      "message": f"Job {name} ran successfully."
    }


  @Command()
  def pods(self, 
           name: args.NAME):
    """List pods for a Job.

    Retrieve all pods that are managed by the specified Job. The pods are filtered by the Job name.

    Usage: CLI Usage
      ```sh
      duploctl job pods <name>
      ```

    Args:
      name: The name of the Job to get pods for.

    Returns:
      list: A list of pods associated with the Job, including their status and metadata.

    Raises:
      DuploError: If the Job could not be found or if there's an error retrieving pods.
    """
    pods = self.__pod_svc.list()
    return [
      pod for pod in pods
      if pod.get("Name", None) == name and pod["ControlledBy"]["QualifiedType"] == "kubernetes:batch/v1/Job"
    ]
