from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("batch_queue")
class DuploBatchQueue(DuploTenantResourceV3):
  """Manage AWS Batch Job Resources

  Run batch jobs as a managed service on AWS infrastructure. 

  Read more docs here: 
  https://docs.duplocloud.com/docs/overview/aws-services/batch
  """

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, 
                     slug="aws/batchJobQueue",
                     prefixed=True)

  def name_from_body(self, body):
    return body["JobQueueName"]
  
  @Command()
  def create(self, body: args.BODY) -> dict:
    """Create a Batch Job Queue.

    Creates a new Batch Job Queue with the specified configuration.

    Usage: Basic CLI Use
      ```sh
      duploctl batch_queue create -f batch_queue.yaml
      ```

    Args:
      body: The configuration for the Batch Job Queue.

    Returns:
      dict: The created Batch Job Queue object.
    """
    arn = super().create(body)
    return {
      "Message": "Batch Job Queue created successfully.",
      "JobQueueArn": arn
    }

  @Command()
  def find(self, 
           name: args.NAME) -> dict:
    """Find a Single Batch Job Queue by name.

    Usage: cli usage
      ```sh
      duploctl batch_queue find <name>
      ```

    Args:
      name: The name of the Batch Job Queue to find.

    Returns: 
      resource: The Batch Job Queue object.
    """
    n = self.prefixed_name(name)
    queues = self.list()
    for q in queues:
      if self.name_from_body(q) == n:
        return q
    raise DuploError(f"Batch Job Queue '{name}' not found", 404)

  @Command()
  def disable(self, 
             name: args.NAME) -> dict:
    """Disable a Batch Compute Environment.

    Usage: cli usage
      ```sh
      duploctl batch_compute delete <name>
      ```
    
    Args:
      name: The name of the Batch Compute Environment to delete.

    Returns: 
      message: A success message.

    Raises:
      DuploError: If the Batch Compute Environment could not be found or deleted. 
    """
    n = self.prefixed_name(name)
    endpoint = f"{self.endpoint()}Disable/{n}"
    self.duplo.delete(endpoint)
    return {
      "message": f"{self.slug}/{name} disabled"
    }