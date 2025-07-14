from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("batch_definition")
class DuploBatchDefinition(DuploTenantResourceV3):
  """Manage AWS Batch Job Definition Resources

  Manage batch Job Definitions as a resource in Duplo. 

  Read more docs here: 
  https://docs.duplocloud.com/docs/overview/aws-services/batch
  """

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, 
                     slug="aws/batchJobDefinition",
                     prefixed=True)

  def name_from_body(self, body):
    return body["JobDefinitionName"]
  
  @Command()
  def list(self) -> list:
    """List all Batch Job Definitions.

    Usage:
      ```sh
      duploctl batch_definition list
      ```

    Example:
      Retrieve all of the revision IDs for one job definition using JMESPATH query and output as yaml
      ```sh
      duploctl batch_definition list --query "[?JobDefinitionName=='duploservices-dev01-myjobdef'].Revision" -o yaml
      ```

    Returns:
      list: A list of Batch Job Definitions.
    """
    return super().list()

  @Command()
  def find(self, 
           name: args.NAME,
           to_revision: args.TO_REVISION = None) -> dict:
    """Find a Single Batch Job Definition by name.

    Usage: cli usage
      ```sh
      duploctl batch_definition find <name>
      ```

    Example:
      Find the previous revision to the latest. This is what you would use to do a rollback. 
      ```sh
      duploctl batch_definition find myjobdef --revision -2
      ```

    Example:
      Find the earliest revision of a job definition.
      ```sh
      duploctl batch_definition find myjobdef --revision 0
      ```

    Args:
      name: The name of the Batch Job Definition to find.
      to_revision: The specific revision of the Batch Job Definition to find. If negative it will walk back that number of revisions from whatever number is the highest revision. The default is -1 which will return the latest. 

    Returns: 
      resource: The Batch Job Definition object.
    """
    # latest will be the default revision, which is -1
    to_rid = -1 if to_revision is None else to_revision
    rid = None
    definitions = self.list()
    n = self.prefixed_name(name)
    revisions = {
      d["Revision"]: d for d in definitions if self.name_from_body(d) == n
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
    """Create a Batch Job Definition resource.

    Usage: CLI Usage
      ```sh
      duploctl batch_definition create -f 'batchdefinition.yaml'
      ```
      Contents of the `batchdefinition.yaml` file
      ```yaml
      --8<-- "src/tests/data/batchdefinition.yaml"
      ```

    Example: One liner example
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/batchdefinition.yaml"
      \"\"\" | duploctl batch_definition create -f -
      ```
    
    Args:
      body: The resource to create.

    Returns: 
      message: Success message.

    Raises:
      DuploError: If the resource could not be created.
    """
    arn = super().create(body)
    rid = int(arn.split(":")[-1])
    name = self.name_from_body(body)
    return {
      "Message": f"Batch Job Definition '{name}' created successfully.",
      "JobDefinitionArn": arn,
      "Revision": rid
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
      n = self.prefixed_name(name)
      if all:
        definitions = self.list()
        rids = [
          d["Revision"] for d in definitions if self.name_from_body(d) == n
        ]
        for rid in rids:
          super().delete(f"{n}:{rid}")
        msg = f"Batch Job Definition '{name}' deleted successfully along with the following revisions: {', '.join(rids)}."
      else:
        resource = self.find(n, to_revision)
        rid = resource["Revision"]
        super().delete(f"{n}:{rid}")
        msg = f"Batch Job Definition '{name}' deleted revision {rid} successfully."
      return {
        "Message": msg
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
    resource = self._to_def_request(self.find(name))
    resource["ContainerProperties"]["Image"] = image
    res = self.create(resource)
    res["Message"] = f"Batch Job Definition '{name}' updated successfully to revision {res['Revision']} with new image '{image}'."
    return res
  
  def _to_def_request(self, body: dict) -> dict:
    # delete the ContainerOrchestrationType, JobDefinitionArn, Revision, and Status
    if "ContainerOrchestrationType" in body:
      del body["ContainerOrchestrationType"]
    if "JobDefinitionArn" in body:
      del body["JobDefinitionArn"]
    if "Revision" in body:
      del body["Revision"]
    if "Status" in body:
      del body["Status"]
    # from ContainerProperties delete the JobRoleArn, Memory, and Vcpus
    if "ContainerProperties" in body:
      container_props = body["ContainerProperties"]
      if "JobRoleArn" in container_props:
        del container_props["JobRoleArn"]
      if "Memory" in container_props:
        del container_props["Memory"]
      if "Vcpus" in container_props:
        del container_props["Vcpus"]
    return body
