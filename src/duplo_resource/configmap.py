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
      duploctl configmap create -f configmap.yaml
      ```
      Contents of the `configmap.yaml` file
      ```yaml
      --8<-- "src/tests/data/configmap.yaml"
      ```
    <b>Examples:</b>

    - Example 1: Create a ConfigMap using a one-liner.
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/configmap.yaml"
      \"\"\" | duploctl configmap create -f -
      ```
    - Example 2: Create a ConfigMap using a file.
      ```sh
      duploctl configmap create -f configmap.yaml
      ```

    <b>Args:</b>

      `name (str, optional)`: Name of the ConfigMap. Required if `body` is not provided.\n
      `body (dict, optional)`: The complete ConfigMap resource definition.\n
      `data (dict, optional)`: Data to merge into the ConfigMap.\n
      `dryrun`: Do not submit any changes to the server.\n
      `wait`: Wait for the resource to be created.

    <b>Returns:</b>

      `dict`: The created resource or success message.

    <b>Raises:</b>

      `DuploError`: If the Configmap could not be created.
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
             patches: args.PATCHES = None,
             dryrun: args.DRYRUN=False) -> dict:
    """
    Update a ConfigMap resource.

    Usage: CLI Usage
      ```sh
      duploctl configmap update -f configmap.yaml
      ```
      Contents of the `configmap.yaml` file
      ```yaml
      --8<-- "src/tests/data/configmap.yaml"
      ```
    <b>Examples:</b> 
    
    - Example 1: Update configmap using a one-liner.
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/configmap.yaml"
      \"\"\" | duploctl configmap update -f -
      ```
    - Example 2: Add new key in the configmap.
      ```sh
      duploctl configmap update <configmap-name> --add data.NewKey NewValue
      ```
    - Example 3: Update existing key from the configmap.
      ```sh
      duploctl configmap update <configmap-name> --replace data.ExistingKey NewValue
      ```
    - Example 4: Delete existing key from the configmap.
      ```sh
      duploctl configmap update <configmap-name> --remove data.ExistingKey
      ```

    <b>Args:</b>

      `name (str, optional)`: Name of the ConfigMap. Required if `body` is not provided.\n
      `body (dict, optional)`: The complete ConfigMap resource definition.\n
      `data (dict, optional)`: Data to merge into the ConfigMap.\n
      `patches`: A list of JSON patches as args to apply to the service.
        The options are `--add`, `--remove`, `--replace`, `--move`, and `--copy`.
        Then followed by `<path>` and `<value>` for `--add`, `--replace`, and `--test`.
      `dryrun (bool, optional)`: If True, return the modified ConfigMap without applying changes.

    <b> Returns:</b>

      `dict`: The updated ConfigMap or a success message.

    <b> Raises:</b>

      `DuploError`: If the ConfigMap update fails.
    """
    if not name:
      raise DuploError("'name' is required.")
    if body:
      if 'metadata' not in body or body['metadata'].get('name') != name:
        raise DuploError("Provided 'name' must match 'metadata.name' in the body.")
    else:
     body = self.find(name)
     if not body:
        raise DuploError(f"ConfigMap '{name}' not found.")

    body.setdefault('data', {}).update(data or {})
    return body if dryrun else super().update(body,patches=patches)

  @Command()
  def find(self,
           name: args.NAME) -> dict:
    """Find a ConfigMap by name and view its content.

    Usage: cli usage
      ```sh
      duploctl configmap find <name>
      ```

    <b>Args:</b>

      `name:` The name of the ConfigMap to find.

    <b>Returns:</b>

      `dict:` The resource content or success message.

    <b>Raises:</b>

      `DuploError:` If the ConfigMap could not be found.
    """
    response = self.duplo.get(self.endpoint(name))
    return response.json()

  @Command()
  def delete(self,
             name: args.NAME) -> dict:
    """
    Deletes the specified ConfigMap by name.

    Usage: cli
      ```sh
      duploctl configmap delete <name>
      ```

    <b>Args:</b>

      `name:` The name of a ConfigMap to delete.

    <b>Returns:</b>

      `message:` Returns a success message if deleted successfully; otherwise, an error.
    """
    super().delete(name)
    return {
      "message": f"Successfully deleted configmap '{name}'"
    }
