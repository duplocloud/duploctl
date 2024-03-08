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

  # @Command()  # Decorator to define a command
  # def update_image(self, name: args.NAME, image: args.IMAGE):  # Method to update the image of a job
  #   """Update the image of a job.
    
  #   Args:
  #     name (str): The name of the job to update.
  #     image (str): The new image to use for the job.
  #   """
  #   tenant_id = self.tenant["TenantId"]  # Getting tenant ID
  #   job = self.find(name)  # Finding job
  #   job["spec"]["template"]["spec"]["containers"][0]["image"] = image  # Updating image
  #   self.duplo.put(f"v3/subscriptions/{tenant_id}/k8s/job/{name}", job)  # Making PUT request to update
  #   return {"message": f"Successfully updated image for job '{name}'"}  # Returning success message
