from duplocloud.client import DuploClient  # Importing necessary modules
from duplocloud.errors import DuploError, DuploFailedResource
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("job")  # Decorator to define a resource
class DuploJob(DuploTenantResourceV3):
  """Kubernetes Jobs

  This class offers methods to manage Kubernetes Jobs within DuploCloud.
  See more details at:
  https://docs.duplocloud.com/docs/kubernetes-overview/jobs
  """
  
  def __init__(self, duplo: DuploClient):  # Constructor method
    super().__init__(duplo, "k8s/job")  
    self.wait_timeout = 1000
    self.wait_poll = 3
    self.__pod_svc = self.duplo.load("pod")

  @Command()  
  def create(self, 
             body: args.BODY, 
             wait: args.WAIT = False):
    """Create a Kubernetes Job.

    Creates a new Kubernetes Job resource managed through DuploCloud.

    Usage: CLI Usage
      ```sh
      duploctl job create -f job.yaml
      ```

    Example: Create a job and wait for it to complete
      ```sh
      duploctl job create -f src/tests/data/job.yaml --wait
      ```

    Args:
      body: The complete Job resource definition in YAML/JSON format.
      wait (bool, optional): If True, wait for the job to complete before returning.
          This is useful for short-running jobs where you want to see the results immediately.

    Returns:
      message: A success message if the job was created successfully.

    Raises:
      DuploError: If the job creation fails.
      DuploFailedResource: If the job fails during execution (when wait=True).
    """
    name = self.name_from_body(body)
    a = 0
    s = 0
    f = 0
    def check_pod_faults(pod, faults):
      """Check if the pod has any faults.
      
      This is for aws and gke because the faults are at the pod level.
      """
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
        raise DuploError(f"Job {name} has no pods {pods_exist} {podct}")
      # check for any faults and show the logs if we can
      faults = self.tenant_svc.faults(id=self.tenant_id)
      for pod in pods:
        check_pod_faults(pod, faults)
        self.__pod_svc.logs(pod=pod)
      # make sure we got all of the logs
      pod_count = active + succeeded + failed
      if podct != pod_count:
        raise DuploError(f"Expected {pod_count} pods, got {podct}")
      if len(fail) > 0:
        raise DuploFailedResource(f"Job {name} failed with {fail[0]['reason']}: {fail[0]['message']}")
      
      # if none have completed, keep waiting
      if not len(cpl) > 0:
        raise DuploError(f"Job {name} not complete {cpl}")
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
      if pod.get("Name", None) == name and pod["ControlledBy"]["QualifiedType"] == "kubernetes:batch/v1/Job"
    ]

  @Command()
  def update(self,
             name: args.NAME,
             patches: args.PATCHES = None,
             suspend_job: args.SUSPEND_JOB = None,
             ttl_seconds_after_finished: args.TTL_SECONDS_AFTER_FINISHED = None,
             dryrun: args.DRYRUN = False) -> dict:
    """Update a Job resource.

    Updates an existing Kubernetes Job with new values for mutable fields.
    Note that many Job fields are immutable after creation, including:
    - spec.template (the entire pod template)
    - spec.selector
    - spec.parallelism
    - spec.completions
    - spec.backoffLimit

    Usage: CLI Usage
      ```sh
      duploctl job update <job-name> [options]
      ```

    Example: Suspend a running job
      ```sh
      duploctl job update <job-name> --suspend-job
      ```

    Example: Resume a suspended job
      ```sh
      duploctl job update <job-name> --resume-job
      ```

    Example: Change TTL after completion
      ```sh
      duploctl job update <job-name> --ttl-seconds-after-finished 3600
      ```

    Example: Use JSON patches to update fields
      ```sh
      duploctl job update <job-name> --add /spec/suspend true
      ```

    Args:
      name: Name of the job to update.
      patches: A list of JSON patches to apply to the job.
        The options are `--add`, `--remove`, `--replace`, `--move`, and `--copy`.
        Then followed by `<path>` and `<value>` for `--add`, `--replace`, and `--test`.
      suspend_job: Use `--suspend-job` to pause job execution or `--resume-job` to continue execution.
      ttl_seconds_after_finished: Time in seconds to automatically delete job after it finishes (use `--ttl-seconds-after-finished` flag).
      dryrun (bool, optional): If True, return the modified job without applying changes.

    Returns:
      message: The updated job or a success message.

    Raises:
      DuploError: If the job update fails or attempts to modify immutable fields.
    """
    job = self.find(name)

    # Apply explicit parameter updates if provided
    if suspend_job is not None:
      if patches is None:
        patches = []

      # Check if the suspend field exists in the job spec
      suspend_exists = job.get('spec', {}).get('suspend') is not None

      # Use 'add' if the field doesn't exist, 'replace' if it does
      op = "replace" if suspend_exists else "add"

      patches.append({
        "op": op,
        "path": "/spec/suspend",
        "value": suspend_job
      })

    if ttl_seconds_after_finished is not None:
      if patches is None:
        patches = []

      # Check if the ttlSecondsAfterFinished field exists in the job spec
      ttl_exists = job.get('spec', {}).get('ttlSecondsAfterFinished') is not None

      # Use 'add' if the field doesn't exist, 'replace' if it does
      op = "replace" if ttl_exists else "add"

      patches.append({
        "op": op,
        "path": "/spec/ttlSecondsAfterFinished",
        "value": ttl_seconds_after_finished
      })

    # If no changes are requested, return the current job
    if patches is None or len(patches) == 0:
      return job

    # Check for attempts to modify immutable fields
    immutable_paths = [
      "/spec/template",
      "/spec/selector",
      "/spec/parallelism",
      "/spec/completions",
      "/spec/backoffLimit"
    ]

    for patch in patches:
      path = patch.get("path", "")
      for immutable_path in immutable_paths:
        if path.startswith(immutable_path):
          raise DuploError(f"Cannot modify immutable field: {path}")

    if dryrun:
      return job

    return super().update(name=name, patches=patches)
