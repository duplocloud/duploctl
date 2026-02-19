from duplocloud.client import DuploClient
from duplocloud.resource import DuploResourceV3
from duplocloud.errors import DuploError, DuploFailedResource, DuploStillWaiting
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("batch_compute", scope="tenant")
class DuploBatchCompute(DuploResourceV3):
  """Manage AWS Batch Job Resources

  Run batch jobs as a managed service on AWS infrastructure. 

  Read more docs here: 
  https://docs.duplocloud.com/docs/overview/aws-services/batch
  """

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, 
                     slug="aws/batchComputeEnvironment", 
                     prefixed=True)

  def name_from_body(self, body):
    return body["ComputeEnvironmentName"]
  
  @Command()
  def create(self, body: args.BODY) -> dict:
    """Create a Batch Compute Environment.

    Creates a new Batch Compute Environment with the specified configuration.

    Usage: Basic CLI Use
      ```sh
      duploctl batch_compute create -f batch_compute.yaml
      ```

    Args:
      body: The configuration for the Batch Compute Environment.

    Returns:
      dict: The created Batch Compute Environment object.
    """
    name = self.name_from_body(body)
    s = None
    def wait_check():
      nonlocal s
      try:
        env = self.find(name)
      except DuploError:
        raise DuploStillWaiting(f"Waiting for Batch Compute Environment '{name}' to be created")
      status_field = env.get("Status", "CREATING")
      status = status_field.get("Value", "CREATING") if isinstance(status_field, dict) else status_field
      if s != status:
        s = status
        self.duplo.logger.warn(f"Batch Compute Environment {name} is {status}")
      if status == "INVALID":
        raise DuploFailedResource(name)
      if status != "VALID":
        raise DuploStillWaiting(f"Batch Compute Environment '{name}' is waiting for status 'VALID'")
    response = super().create(body, wait_check)
    return {
      "Message": "Batch Compute Environment created successfully.",
      "ComputeEnvironmentArn": response
    }
  
  @Command()
  def find(self, 
           name: args.NAME) -> dict:
    """Find a Single Batch Compute Environment by name.
    
    Usage: cli usage
      ```sh
      duploctl batch_compute find <name>
      ```

    Args:
      name: The name of the Batch Compute Environment to find.
    
    Returns: 
      resource: The Batch Compute Environment object.
    """
    n = self.prefixed_name(name)
    envs = self.list()
    for env in envs:
      if self.name_from_body(env) == n:
        return env
    raise DuploError(f"Batch Compute Environment '{name}' not found", 404)
  
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
      "message": f"Batch Compute Environment '{name}' disabled"
    }