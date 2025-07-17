from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("batch_job")
class DuploBatchJob(DuploTenantResourceV3):
  """Manage AWS Batch Job Resources

  Run batch jobs as a managed service on AWS infrastructure. 

  Read more docs here: 
  https://docs.duplocloud.com/docs/overview/aws-services/batch
  """

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, 
                     slug="aws/batchJobs",
                     prefixed=True)

  def name_from_body(self, body):
    return body["JobName"]

  @Command()
  def list(self,
           queue: args.BATCH_QUEUE = None,
           all: args.ALL = False) -> list:
    """List all Batch Job Definitions.

    Usage:
      ```sh
      duploctl batch_job list <queue_name>
      ```
    
    Args:
      queue_name: The name of the Batch Queue for this list of jobs.
      all: If true, list all jobs in all queues.

    Returns:
      list: A list of Batch Job Definitions.
    """
    def get_job_list(qn):
      response = self.duplo.get(self.endpoint(qn))
      return response.json()
    if not queue and not all:
      raise DuploError("You must specify a queue name with --queue <queue_name> or use --all to list jobs in all queues.")
    if queue:
      return get_job_list(self.prefixed_name(queue))
    else:
      queue_svc = self.duplo.load("batch_queue")
      queues = queue_svc.list()
      jobs = []
      for q in queues:
        j = get_job_list(queue_svc.name_from_body(q))
        jobs.extend(j)
      return jobs

  @Command()
  def find(self, 
           name: args.NAME = None,
           queue: args.BATCH_QUEUE = None) -> dict:
    """Find a Single Batch Job by name.

    Usage: cli usage
      ```sh
      duploctl batch_definition find <name> <queue_name>
      ```

    Args:
      name: The name of the Batch Job Definition to find.
      queue_name: The name of the Batch Queue for this job.
      to_revision: The specific revision of the Batch Job Definition to find. If negative it will walk back that number of revisions from whatever number is the highest revision.

    Returns: 
      resource: The Batch Job Definition object.
    """
    jobs = self.list(queue)
    n = self.prefixed_name(name)
    for job in jobs:
      if self.name_from_body(job) == n:
        return job
    raise DuploError(f"Batch Job '{name}' not found in queue '{queue}'", 404)

  @Command()
  def create(self, 
             body: args.BODY) -> dict:
    """Create a Batch Job resource.

    Usage: CLI Usage
      ```sh
      duploctl batch_job create -f 'batchjob.yaml'
      ```
      Contents of the `batchjob.yaml` file
      ```yaml
      --8<-- "src/tests/data/batchjob.yaml"
      ```

    Example: One liner example
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/batchjob.yaml"
      \"\"\" | duploctl batch_job create -f -
      ```
    
    Args:
      body: The resource to create.

    Returns: 
      message: Success message.

    Raises:
      DuploError: If the resource could not be created.
    """
    queue = body.get("JobQueue", None)
    definition = body.get("JobDefinition", None)
    if not (queue and definition):
      raise DuploError("You must specify both JobQueue and JobDefinition in the body to create a Batch Job.")
    body["JobQueue"] = self.prefixed_name(queue)
    if not definition.startswith("arn:aws:batch:"):
      body["JobDefinition"] = self._job_definition_arn(definition)
    id = super().create(body)
    return {
      "Message": f"Batch Job '{self.name_from_body(body)}' created successfully.",
      "JobId": id
    }

  def _job_definition_arn(self, definition: str) -> str:
    def_name_parts = definition.split(":")
    # make sure there is either one or two parts only
    if len(def_name_parts) not in [1, 2]:
      raise DuploError(f"When the JobDefinition is not an arn, the name may only have one optional colon where the value after is the revision id: {definition}")
    def_name = self.prefixed_name(def_name_parts[0])
    rid = def_name_parts[1] if len(def_name_parts) == 2 else None
    # find the def using the def service
    job_def_svc = self.duplo.load("batch_definition")
    job_def = job_def_svc.find(def_name, rid)
    return job_def["JobDefinitionArn"]
