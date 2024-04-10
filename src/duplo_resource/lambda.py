from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV2
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("lambda")
class DuploLambda(DuploTenantResourceV2):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self):
    """Retrieve a list of all lambdas in a tenant."""
    tenant_id = self.tenant["TenantId"]
    tenant_name = self.tenant["AccountName"]
    response = self.duplo.get(f"subscriptions/{tenant_id}/GetLambdaFunctions")
    if (data := response.json()):
      return data
    else:
      raise DuploError(f"No lambda functions found in tenant '{tenant_name}'", 404)
  
  @Command()
  def find(self, 
           name: args.NAME):
    """Find a Lambda function by name.
    
    Args:
      name (str): The name of the lambda to find.
    Returns: 
      The lambda object.
    Raises:
      DuploError: If the lambda could not be found.
    """
    try:
      return [s for s in self.list() if s["FunctionName"] == name][0]
    except IndexError:
      raise DuploError(f"Lambda '{name}' not found", 404)
    
  @Command()
  def create(self, 
             body: args.BODY,
             wait: args.WAIT = False):
    """Create a new tenant."""
    def wait_check():
      name = self.name_from_body(body)
      self.find(name)
    tenant_id = self.tenant["TenantId"]
    self.duplo.post(f"subscriptions/{tenant_id}/CreateLambdaFunction", body)
    if wait:
      self.wait(wait_check, 400)
    return {
      "message": f"Lambda {body['FunctionName']} created"
    }
  
  @Command()
  def delete(self, 
             name: args.NAME):
    """Delete a lambda."""
    tenant_id = self.tenant["TenantId"]
    self.duplo.post(f"subscriptions/{tenant_id}/DeleteLambdaFunction/{name}")
    return {
      "message": f"Lambda {name} deleted"
    }

  @Command()
  def update_image(self, 
                   name: args.NAME, 
                   image: args.IMAGE):
    """Update the image of a lambda.
    
    Args:
      name (str): The name of the lambda to update.
      image (str): The new image to use for the lambda.
    """
    tenant_id = self.tenant["TenantId"]
    data = {
      "FunctionName": name,
      "ImageUri": image
    }
    response = self.duplo.post(f"subscriptions/{tenant_id}/UpdateLambdaFunction", data)
    return response.json()

  @Command()
  def update_s3(self, 
                   name: args.NAME, 
                   bucket: args.S3BUCKET,
                   key: args.S3KEY):
    """Update the s3 bucket and key of a lambda.
    
    Args:
      name (str): The name of the lambda to update.
      s3bucket (str): The s3 bucket to use for the lambda.
      s3key (str): The s3 key (file path) to use for the lambda.
    """
    tenant_id = self.tenant["TenantId"]
    data = {
      "FunctionName": name,
      "S3Bucket": bucket,
      "S3Key": key
    }
    response = self.duplo.post(f"subscriptions/{tenant_id}/UpdateLambdaFunction", data)
    return response.json()

  def name_from_body(self, body):
    prefix = f"duploservices-{self.duplo.tenant}"
    name =  body["FunctionName"]
    if not name.startswith(prefix):
      name = f"{prefix}-{name}"
    return name
