from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("s3")
class DuploS3(DuploTenantResourceV3):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "aws/s3bucket")

  @Command()  
  def create(self, 
             body: args.BODY):
    """Create a job."""
    name = self.name_from_body(body)
    print("Running create")
    super().create(body)
    return {
      "message": f"Bucket {name} created successfully."
    }

  def name_from_body(self, body):
    return body["Name"]