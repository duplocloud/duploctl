from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.errors import DuploError, DuploFailedResource, DuploStillWaiting
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
    super().__init__(duplo, "aws/batchJobQueue")

  def name_from_body(self, body):
    return body["JobQueueName"]
  
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
    queues = self.list()
    for q in queues:
      if self.name_from_body(q) == name:
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
    endpoint = f"{self.endpoint()}Disable/{name}"
    self.duplo.delete(endpoint)
    return {
      "message": f"{self.slug}/{name} disabled"
    }