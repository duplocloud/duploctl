from duplocloud.client import DuploClient  # Importing necessary modules
from duplocloud.resource import DuploTenantResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args  # Importing necessary modules

@Resource("job")  # Decorator to define a resource
class DuploJob(DuploTenantResource):
  
  def __init__(self, duplo: DuploClient):  # Constructor method
    super().__init__(duplo)  # Calling superclass constructor
  
  @Command()  # Decorator to define a command
  def list(self):  # Method to list all jobs
    """Retrieve a list of all jobs in a tenant."""
    tenant_id = self.tenant["TenantId"]  # Getting tenant ID
    response = self.duplo.get(f"v3/subscriptions/{tenant_id}/k8s/job")  # Making GET request
    return response.json()  # Returning JSON response
  
  @Command()  # Decorator to define a command
  def find(self, name: args.NAME):  # Method to find a job by name
    """Find a job by name.
    
    Args:
      name (str): The name of the job to find.
    Returns: 
      The job object.
    Raises:
      DuploError: If the job could not be found.
    """
    tenant_id = self.tenant["TenantId"]  # Getting tenant ID
    response = self.duplo.get(f"v3/subscriptions/{tenant_id}/k8s/job/{name}")  # Making GET request
    return response.json()  # Returning JSON response

  @Command()  # Decorator to define a command
  def create(self, body: args.BODY):  # Method to create a new job
    """Create a new job.
    
    Args:
      job_config (dict): The configuration for the new job.
    Returns: 
      A message indicating the successful creation of the job.
    """
    tenant_id = self.tenant["TenantId"]  # Getting tenant ID
    job_name = body.get('JobName', 'Unnamed Job')  # Getting job name from job configuration
    self.duplo.post(f"v3/subscriptions/{tenant_id}/k8s/job", body)  # Making POST request with job configuration
    return {
      "message": f"Job {job_name} created"  # Returning message with job name
    }
