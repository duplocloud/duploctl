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
      dict: The created resource or success message.
    Raises:
      DuploError: If the Configmap could not be created.
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

  @Command()
  def update(self,
             name: args.NAME,
             body: args.BODY=None,
             data: args.DATAMAP=None,
             dryrun: args.DRYRUN=False) -> dict:
    """
    Update a ConfigMap resource.
    Usage: CLI Usage
      ```sh
      duploctl configmap update -f 'configmap.yaml'
      ```
      Contents of the `configmap.yaml` file
      ```yaml
      --8<-- "src/tests/data/configmap.yaml"
      ```
    Example: One liner example
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/configmap.yaml"
      \"\"\" | duploctl configmap update -f -
      ```
    Args:
      name (str, optional): Name of the ConfigMap. Required if `body` is not provided.
      body (dict, optional): The complete ConfigMap resource definition.
      data (dict, optional): Data to merge into the ConfigMap.
      dryrun (bool, optional): If True, return the modified ConfigMap without applying changes.

    Returns:
      dict: The updated ConfigMap or a success message.

    Raises:
      DuploError: If the ConfigMap update fails.
    """
    if not name:
      raise DuploError("'name' is required.")
    if body:
      if 'metadata' not in body or body['metadata'].get('name') != name:
        raise DuploError("Provided 'name' must match 'metadata.name' in the body.")
    else:
      body = {'metadata': {'name': name}, 'data': {}}
    body.setdefault('data', {}).update(data or {})
    return body if dryrun else super().update(body)

  @Command()
  def find(self,
           name: args.NAME) -> dict:
    """Find a ConfigMap by name and return it's content.
    Usage: cli usage
      ```sh
      duploctl configmap find <name>
      ```
    Args:
      name: The name of the ConfigMap to find.
    Returns:
      dict: The resource content or success message.
    Raises:
      DuploError: If the ConfigMap could not be found.
    """
    response = self.duplo.get(self.endpoint(name))
    return response.json()

  @Command()
  def delete(self,
             name: args.NAME) -> dict:
    """Delete a ConfigMap.
    Deletes a ConfigMap by name.
    Usage: cli
      ```sh
      duploctl configmap delete <name>
      ```
    Args:
      name: The name of a ConfigMap to delete.
    Returns:
      message: A success message.
    """
    super().delete(name)
    return {
      "message": f"Successfully deleted configmap '{name}'"
    }
