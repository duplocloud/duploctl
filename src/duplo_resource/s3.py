from duplocloud.controller import DuploCtl
from duplocloud.resource import DuploResourceV3
from duplocloud.commander import Command, Resource
from duplocloud.errors import DuploError
import duplocloud.args as args


@Resource("s3", scope="tenant")
class DuploS3(DuploResourceV3):
  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo, "aws/s3Bucket")

  def name_from_body(self, body):
    return body["Name"]

  @Command()
  def find(self, name: args.NAME) -> dict:
    """Find an S3 bucket by name.

    Usage: CLI Usage
      ```sh
      duploctl s3 find <name>
      ```

    Args:
      name: The full bucket name (e.g. duploservices-tenant-mybucket).

    Returns:
      bucket: The S3 bucket object.

    Raises:
      DuploError: If the bucket could not be found.
    """
    response = self.client.get(self.endpoint(name))
    return response.json()

  @Command()
  def delete(self, name: args.NAME) -> dict:
    """Delete an S3 bucket by name.

    Usage: CLI Usage
      ```sh
      duploctl s3 delete <name>
      ```

    Args:
      name: The full bucket name (e.g. duploservices-tenant-mybucket).

    Returns:
      message: A success message.

    Raises:
      DuploError: If the bucket could not be deleted.
    """
    self.client.delete(self.endpoint(name).replace("aws/s3Bucket", "aws/s3bucket"))
    return {"message": f"S3 bucket '{name}' deleted"}