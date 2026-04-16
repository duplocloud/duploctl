from duplocloud.controller import DuploCtl
from duplocloud.resource import DuploResourceV3
from duplocloud.errors import DuploError
from duplocloud.commander import Resource, Command
import duplocloud.args as args

@Resource("batch_scheduling_policy", scope="tenant")
class DuploBatchSchedulingPolicy(DuploResourceV3):
  """Manage AWS Batch Scheduling Policies

  Run batch jobs as a managed service on AWS infrastructure.

  Read more docs here:
  https://docs.duplocloud.com/docs/automation-platform/overview/aws-services/batch
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo,
                     slug="aws/batchSchedulingPolicy",
                     prefixed=True)

  def name_from_body(self, body):
    return body["Name"]

  @Command()
  def update(self,
             name: args.NAME = None,
             body: args.BODY = None,
             patches: args.PATCHES = None) -> dict:
    """Update a Batch Scheduling Policy.

    The DuploCloud backend expects PUT to the collection endpoint
    with the resource identified by the body, not by the URL path.

    Usage: CLI Usage
      ```sh
      duploctl batch_scheduling_policy update <name>
      ```

    Args:
      name: The name of the scheduling policy to update.
      body: The scheduling policy body.
      patches: The patches to apply to the resource.

    Returns:
      resource: The updated scheduling policy.

    Raises:
      DuploError: If the scheduling policy could not be updated.
    """
    if not name and not body:
      raise DuploError("Name is required when body is not provided")
    name = name or self.name_from_body(body)
    current = self.find(name)
    if body:
      current.update(body)
    if patches:
      current = self.duplo.jsonpatch(current, patches)
    current["Name"] = self.prefixed_name(name)
    response = self.client.put(self.endpoint(), current)
    return response.json()
