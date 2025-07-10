from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.errors import DuploError, DuploFailedResource, DuploStillWaiting
from duplocloud.commander import Command, Resource
import duplocloud.args as args

def revision_id(d: dict) -> int:
  return int(d["JobDefinitionArn"].split(":")[-1])

@Resource("batch_definition")
class DuploBatchDefinition(DuploTenantResourceV3):
  """Manage AWS Batch Job Resources

  Run batch jobs as a managed service on AWS infrastructure. 

  Read more docs here: 
  https://docs.duplocloud.com/docs/overview/aws-services/batch
  """

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "aws/batchJobDefinition")

  def name_from_body(self, body):
    return body["JobDefinitionName"]

  @Command()
  def find(self, 
           name: args.NAME,
           to_revision: args.TO_REVISION = None) -> dict:
    """Find a Single Batch Job Definition by name.

    Usage: cli usage
      ```sh
      duploctl batch_definition find <name>
      ```

    Args:
      name: The name of the Batch Job Definition to find.
      to_revision: The specific revision of the Batch Job Definition to find. If negative it will walk back that number of revisions from whatever number is the highest revision.

    Returns: 
      resource: The Batch Job Definition object.
    """
    # latest will be the default revision, which is -1
    to_rid = -1 if to_revision is None else to_revision
    rid = None
    definitions = self.list()
    revisions = {
      revision_id(d): d for d in definitions if self.name_from_body(d) == name
    }
    rids = sorted(revisions.keys())
    if len(rids) == 0:
      raise DuploError(f"Batch Job Definition '{name}' not found", 404)
    
    # if to_revision is negative or 0, we will walk back that many revisions
    if to_rid <= 0:
      # try but catch the index out of range exception
      try:
        rid = rids[to_rid]
      except IndexError:
        raise DuploError(f"Batch Job Definition '{name}' does not go back {to_rid} revisions. The furthest back is -{len(rids)} to revision number {rids[0]}", 404)
    # if to_revision is positive, we will just find that revision if it exists in the list
    elif to_rid > 0:
      rid = to_rid

    # finally return it if it exists
    if rid not in rids:
      raise DuploError(f"Batch Job Definition '{name}' revision {rid} not found. The latest is {rids[-1]}", 404)
    else:
      return revisions[rid]

  @Command()
  def create(self, 
             body: args.BODY) -> dict:
    """Create a {{kind}} resource.

    Usage: CLI Usage
      ```sh
      duploctl batch_definition create -f 'batch_definition.yaml'
      ```
      Contents of the `batch_definition.yaml` file
      ```yaml
      --8<-- "src/tests/data/batch_definition.yaml"
      ```

    Example: One liner example
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/batch_definition.yaml"
      \"\"\" | duploctl batch_definition create -f -
      ```
    
    Args:
      body: The resource to create.
      wait: Wait for the resource to be created.
      wait_check: A callable function to check if the resource

    Returns: 
      message: Success message.

    Raises:
      DuploError: If the resource could not be created.
    """
    arn = super().create(body)
    return {
      "message": "Batch Job Definition created successfully.",
      "JobDefinitionArn": arn
    }
  
  @Command()
  def delete(self,
              name: args.NAME,
              to_revision: args.TO_REVISION = None,
              all: args.ALL = False) -> dict:
      """Delete a Batch Job Definition by name.
  
      Usage: CLI Usage
        ```sh
        duploctl batch_definition delete <name>
        ```
  
      Args:
        name: The name of the Batch Job Definition to delete.
        to_revision: The specific revision of the Batch Job Definition to delete. If negative it will walk back that number of revisions from whatever number is the highest revision.
  
      Returns: 
        message: Success message.
      """
      if all:
        definitions = self.list()
        revisions = [
          revision_id(d) for d in definitions if self.name_from_body(d) == name
        ]
        for rid in revisions:
          super().delete(f"{name}:{rid}")
        msg = f"Batch Job Definition '{name}' deleted successfully along with the following revisions: {', '.join(revisions)}."
      else:
        resource = self.find(name, to_revision)
        rid = revision_id(resource)
        super().delete(f"{name}:{rid}")
        msg = f"Batch Job Definition '{name}' deleted revision {rid} successfully."
      return {
        "message": msg
      }
  
  @Command()
  def update_image(self,
                  name: args.NAME,
                  image: args.IMAGE) -> dict:
    """Update the image of a Batch Job Definition by name.
  
    Usage: CLI Usage
      ```sh
      duploctl batch_definition update_image <name> --image <image>
      ```
  
    Args:
      name: The name of the Batch Job Definition to update.
      image: The new image to set for the Batch Job Definition.
  
    Returns: 
      message: Success message.
    """
    resource = self.find(name)
    resource["ContainerProperties"]["Image"] = image
    res = self.create(resource)
    rid = revision_id(res)
    return {
      "Message": f"Batch Job Definition '{name}' updated successfully to revision {rid} with new image '{image}'.",
      "JobDefinitionArn": res["JobDefinitionArn"],
      "RevisionId": rid
    }
