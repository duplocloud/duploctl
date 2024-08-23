from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("configmap")
class DuploConfigMap(DuploTenantResourceV3):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "k8s/configmap")

  @Command()
  def create(self, 
             name: args.NAME=None,
             body: args.BODY=None,
             data: args.DATAMAP=None,
             dryrun: args.DRYRUN=False,
             wait: args.WAIT=False) -> dict:
    """Create a Configmap resource.

    Usage: CLI Usage
      ```sh
      duploctl configmap create -f 'configmap.yaml'
      ```
      Contents of the `configmap.yaml` file
      ```yaml
      --8<-- "src/tests/data/configmap.yaml"
      ```

    Example: One liner example
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/configmap.yaml"
      \"\"\" | duploctl configmap create -f -
      ```
    
    Args:
      name: The name to set the configmap to.
      body: The resource to create.
      data: The data to add to the configmap.
      dryrun: Do not submit any changes to the server.
      wait: Wait for the resource to be created.

    Returns: 
      message: Success message.

    Raises:
      DuploError: If the resource could not be created.
    """
    if not name and not body:
      raise DuploError("Name is required when body is not provided")
    if not body:
      body = {}
    # make sure the body has a metadata key
    if 'metadata' not in body:
      body['metadata'] = {}
    # also make sure the data key is present
    if 'data' not in body:
      body['data'] = {}
    if name:
      body['metadata']['name'] = name
    if data:
      body['data'].update(data)
    if dryrun:
      return body
    else:
      return super().create(body, wait=wait)

