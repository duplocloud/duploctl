from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("configmap")
class DuploConfigMap(DuploTenantResourceV3):
  """Kubernetes ConfigMaps
  
  This class offers methods to manage Kubernetes ConfigMaps within DuploCloud.

  See more details at:
  https://docs.duplocloud.com/docs/kubernetes-overview/configs-and-secrets
  """

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "k8s/configmap")

  @Command()
  def create(self, 
             name: args.NAME=None,
             body: args.BODY=None,
             data: args.DATAMAP=None,
             dryrun: args.DRYRUN=False,) -> dict:
    """Create a Configmap resource.

    Creates a new kubernetes ConfigMap resource with the specified metadata and data entries.

    Usage: CLI Usage
      ```sh
      duploctl configmap create -f configmap.yaml
      ```
      Contents of the `configmap.yaml` file
      ```yaml
      --8<-- "src/tests/data/configmap.yaml"
      ```

    Example: Create a ConfigMap using a one-liner.
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/configmap.yaml"
      \"\"\" | duploctl configmap create -f -
      ```

    Example: Create a ConfigMap using a file.
      ```sh
      duploctl configmap create -f configmap.yaml
      ```

    Example: Create a ConfigMap by specifying key-value pairs as literals.
      ```sh
      duploctl configmap create <configmap-name> --from-literal Key1="Val1" --from-literal Key2="Val2"
      ```

    Example: Create a ConfigMap from a file.
      ```sh
      duploctl configmap create <configmap-name> --from-file config-map.txt
      ```

    Args:
      name: Name of the ConfigMap. Required if `body` is not provided.
      body: The complete ConfigMap resource definition.
      data: Data to merge into the ConfigMap.
      dryrun: Do not submit any changes to the server.

    Returns:
      message: The created resource or success message.

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
      return super().create(body)

  @Command()
  def update(self,
             name: args.NAME,
             body: args.BODY=None,
             data: args.DATAMAP=None,
             patches: args.PATCHES = None,
             dryrun: args.DRYRUN=False) -> dict:
    """Updates a ConfigMap resource.

    This function allows you to modify the contents of a ConfigMap without deleting
    or recreating it.

    Usage: CLI Usage
      ```sh
      duploctl configmap update -f configmap.yaml
      ```
      Contents of the `configmap.yaml` file
      ```yaml
      --8<-- "src/tests/data/configmap.yaml"
      ```

    Example: Update configmap using a one-liner.
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/configmap.yaml"
      \"\"\" | duploctl configmap update -f -
      ```

    Example: Add new key in the configmap.
      ```sh
      duploctl configmap update <configmap-name> --add /data/NewKey NewValue
      ```

    Example: Update existing key from the configmap.
      ```sh
      duploctl configmap update <configmap-name> --replace /data/ExistingKey NewValue
      ```

    Example: Delete existing key from the configmap.
      ```sh
      duploctl configmap update <configmap-name> --remove /data/ExistingKey
      ```

    Example: Update a ConfigMap by specifying key-value pairs as literals.
      ```sh
      duploctl configmap update <configmap-name> --from-literal Key1="Val1" --from-literal Key2="Val2"
      ```

    Example: Update a ConfigMap from a file.
      ```sh
      duploctl configmap update <configmap-name> --from-file config-map.txt
      ```

    Args:
      name: Name of the ConfigMap. Required if `body` is not provided.
      body: The complete ConfigMap resource definition.
      data: Data to merge into the ConfigMap.
      patches: A list of JSON patches as args to apply to the service.
        The options are `--add`, `--remove`, `--replace`, `--move`, and `--copy`.
        Then followed by `<path>` and `<value>` for `--add`, `--replace`, and `--test`.
      dryrun (bool, optional): If True, return the modified ConfigMap without applying changes.

    Returns:
      message: The updated ConfigMap or a success message.

    Raises:
      DuploError: If the ConfigMap update fails.
    """
    if data:
      if not name:
        raise DuploError("Name is required when body is not provided")
      body = self.find(name)
      body.setdefault('data', {}).update(data or {})
    return body if dryrun else super().update(name=name, body=body, patches=patches)

  @Command()
  def find(self,
           name: args.NAME) -> dict:
    """Find a ConfigMap.

    Retrieve details of a specific ConfigMap by name

    Usage: cli usage
      ```sh
      duploctl configmap find <name>
      ```

    Args:
      name: The name of the ConfigMap to find.

    Returns:
      message: The resource content or success message.

    Raises:
      DuploError: ConfigMap not found.
    """
    try:
      response = self.duplo.get(self.endpoint(name))
    except DuploError as e:
      raise DuploError(f"Failed to find ConfigMap '{name}': {str(e)}")
    return response.json()

  @Command()
  def delete(self,
             name: args.NAME) -> dict:
    """Delete ConfigMap

    Deletes the specified ConfigMap by name.

    Usage: cli
      ```sh
      duploctl configmap delete <name>
      ```

    Args:
      name: The name of a ConfigMap to delete.

    Returns:
      message: Returns a success message if deleted successfully; otherwise, an error.
    """
    super().delete(name)
    return {
      "message": f"Successfully deleted configmap '{name}'"
    }
