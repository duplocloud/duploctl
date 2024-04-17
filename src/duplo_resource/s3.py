from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV2
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("s3")
class DuploS3(DuploTenantResourceV2):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)

  @Command()
  def list(self):
    """Retrieve a list of all infrastructures in the Duplo system."""
    tenant_id = self.tenant["TenantId"]
    tenant_name = self.tenant["AccountName"]
    response = self.duplo.get(f"v3/subscriptions/{tenant_id}/aws/s3Bucket")
    if (data := response.json()):
      return data
    else:
      raise DuploError(f"No s3 bucket found in tenant '{tenant_name}'", 404)
    
  
  @Command()
  def create(self, 
             body: args.BODY,
             wait: args.WAIT = False):
    """Create a new s3."""
    def wait_check():
      name = self.name_from_body(body)
      self.find(name)
    tenant_id = self.tenant["TenantId"]
    self.duplo.post(f"v3/subscriptions/{tenant_id}/aws/s3Bucket", body)
    if wait:
      self.wait(wait_check, 400)
    return {
      "message": f"S3 Bucket with name {body['Name']} created"
    }
  
  @Command()
  def delete(self, 
             name: args.NAME):
    """Delete a s3."""
    tenant_id = self.tenant["TenantId"]
    self.duplo.delete(f"v3/subscriptions/{tenant_id}/aws/s3Bucket/{name}")
    return {
      "message": f"S3 Bucket with name {name} deleted"
    }
  
  @Command()
  def update(self, 
             name: args.NAME,
             body: args.BODY = None,
             wait: args.WAIT = False):
    """Update a s3 bucket."""
    def wait_check():
      name = self.name_from_body(body)
      self.find(name)
    tenant_id = self.tenant["TenantId"]
    if (name is None and body is None):
      raise DuploError("No arguments provided to update service", 400)
    if name and body:
      body["Name"] = name
    if body is None:
      body = self.find(name)
    self.duplo.put(f"v3/subscriptions/{tenant_id}/aws/s3Bucket/{name}", body)
    if wait:
      self.wait(wait_check, 400)
    return {
      "message": f"S3 Bucket with name {body['Name']} updated"
    }

    
    
 
  
