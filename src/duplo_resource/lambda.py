from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.errors import DuploError

class DuploLambda(DuploResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self.tenent_svc = duplo.service('tenant')
  
  def list(self):
    """Retrieve a list of all lambdas in a tenant."""
    tenant_id = self.get_tenant()["TenantId"]
    return self.duplo.get(f"subscriptions/{tenant_id}/GetLambdaFunctions")
  
  def find(self, lambda_name):
    """Find a Lambda function by name.
    
    Args:
      lambda_name (str): The name of the lambda to find.
    Returns: 
      The lambda object.
    Raises:
      DuploError: If the lambda could not be found.
    """
    try:
      return [s for s in self.list() if s["FunctionName"] == lambda_name][0]
    except IndexError:
      raise DuploError(f"Lambda '{lambda_name}' not found", 404)

  def update_image(self, lambda_name, image):
    """Update the image of a lambda.
    
    Args:
      lambda_name (str): The name of the lambda to update.
      image (str): The new image to use for the lambda.
    """
    tenant_id = self.get_tenant()["TenantId"]
    data = {
      "FunctionName": lambda_name,
      "ImageUri": image
    }
    return self.duplo.post(f"subscriptions/{tenant_id}/UpdateLambdaFunction", data)
