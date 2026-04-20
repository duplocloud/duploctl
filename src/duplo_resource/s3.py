from duplocloud.controller import DuploCtl
from duplocloud.resource import DuploResourceV3
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("s3", scope="tenant")
class DuploS3(DuploResourceV3):
  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo, "aws/s3Bucket")
    self._aws_account_id = None

  def name_from_body(self, body):
    return body["Name"]

  def _account_id(self) -> str:
    """Resolve the AWS account ID from system info, cached on the instance."""
    if not self._aws_account_id:
      sys_info = self.duplo.load("system").info()
      account_id = sys_info.get("DefaultAwsAccount")
      if not account_id:
        raise DuploError(
          "Could not resolve AWS account ID from system info; "
          "pass the full bucket name "
          "(duploservices-<tenant>-<name>-<account_id>) instead.",
          500,
        )
      self._aws_account_id = str(account_id)
    return self._aws_account_id

  @Command()
  def find(self, name: args.NAME) -> dict:
    """Find an S3 bucket by name.

    Accepts either the short name (e.g. mybucket) or the full
    AWS bucket name (e.g. duploservices-tenant-mybucket-123456).

    Resolution order:
      1. Try the name as-is via the single-bucket GET endpoint.
      2. On 404, build the full name using the tenant prefix and AWS
         account ID, and retry the single-bucket GET.
      3. If still 404, raise DuploNotFound.

    Usage: CLI Usage
      ```sh
      duploctl s3 find <name>
      ```

    Args:
      name: The bucket name (short or full form).

    Returns:
      bucket: The S3 bucket object.

    Raises:
      DuploNotFound: If the bucket could not be found.
    """
    try:
      return self.client.get(self.endpoint(name)).json()
    except DuploNotFound:
      pass
    full_name = f"{self.prefixed_name(name)}-{self._account_id()}"
    if full_name == name:
      raise DuploNotFound(name, "s3")
    try:
      return self.client.get(self.endpoint(full_name)).json()
    except DuploNotFound:
      raise DuploNotFound(name, "s3")

  @Command()
  def update(self,
             name: args.NAME = None,
             body: args.BODY = None,
             patches: args.PATCHES = None) -> dict:
    """Update an S3 bucket.

    Usage: CLI Usage
      ```sh
      duploctl s3 update -f 's3.yaml'
      ```

    Args:
      name: The name of the bucket to update.
      body: The updated bucket configuration.
      patches: The patches to apply to the bucket.

    Returns:
      dict: The updated bucket details.

    Raises:
      DuploError: If the bucket could not be updated.
    """
    if not name and not body:
      raise DuploError("Name is required when body is not provided")
    name = name if name else self.name_from_body(body)
    current = self.find(name)
    full_name = self.name_from_body(current)
    if body:
      body["Name"] = full_name
    else:
      body = current
    if patches:
      body = self.duplo.jsonpatch(body, patches)
    response = self.client.put(
      self.endpoint(full_name),
      body
    )
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
    full_name = self.name_from_body(self.find(name))
    self.client.delete(self.endpoint(full_name))
    return {"message": f"S3 bucket '{full_name}' deleted"}
