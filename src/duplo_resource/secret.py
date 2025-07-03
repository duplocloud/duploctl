from duplocloud import args
from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource

@Resource("secret")
class DuploSecret(DuploTenantResourceV3):
  """Kubernetes Secrets
  
  This class provides methods to manage Kubernetes Secrets in DuploCloud.
  
  See more details at: 
  https://docs.duplocloud.com/docs/kubernetes-overview/configs-and-secrets/setting-kubernetes-secrets
  """
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "k8s/secret")

  def name_from_body(self, body):
    return body["SecretName"]
  
  @Command()
  def create(self, 
             name: args.NAME=None,
             body: args.BODY=None,
             data: args.DATAMAP=None,
             dryrun: args.DRYRUN=False) -> dict:
    """Create a Secret

    Create a new Kubernetes secret managed through DuploCloud.

    Usage: CLI Usage
      ```sh
      duploctl secret create -f secret.yaml
      ```
      Contents of the `secret.yaml` file
      ```yaml
      --8<-- "src/tests/data/secret.yaml"
      ```

    Example: Create a secret using a one-liner.
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/secret.yaml"
      \"\"\" | duploctl secret create -f -
      ```

    Example: Create a secret using a file.
      ```sh
      duploctl secret create -f secret.yaml
      ```

    Example: Create a secret by specifying key-value pairs as literals.
      ```sh
      duploctl secret create <secret-name> --from-literal Key1="Val1" --from-literal Key2="Val2"
      ```

    Example: Create a secret from a file.
      ```sh
      duploctl secret create <secret-name> --from-file secret-map.txt
      ```

    Args:
      name: Name of the secret. Required if `body` is not provided.
      body: The complete secret resource definition.
      data: Data to merge into the secret.
      dryrun: If True, return the modified secret without applying changes.

    Returns:
      message: The updated secret or a success message.

    Raises:
      DuploError: If the secret create fails.
    """
    if not name and not body:
      raise DuploError("Name is required when body is not provided")
    if not body:
      body = {}
    # also make sure the data key is present
    if 'SecretData' not in body:
      body['SecretData'] = {}
    if name:
      body['SecretName'] = name
    if data:
      body['SecretData'].update(data)
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
    """Updates a secret resource.

    Updates an existing Kubernetes Secret resource with new or modified data.

    Usage: CLI Usage
      ```sh
      duploctl secret update -f secret.yaml
      ```
      Contents of the `secret.yaml` file
      ```yaml
      --8<-- "src/tests/data/secret.yaml"
      ```

    Example: Update secret using a one-liner.
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/secret.yaml"
      \"\"\" | duploctl secret update -f -
      ```

    Example: Add new keys in the secret.
      ```sh
      duploctl secret update <secret-name> --add /SecretData/NewKey1 NewValue1 --add /SecretData/NewKey2 NewValue2
      ```

    Example: Update existing keys from the secret.
      ```sh
      duploctl secret update <secret-name> --replace /SecretData/ExistingKey1 NewValue1 --replace /SecretData/ExistingKey2 NewValue2
      ```

    Example: Delete existing keys from the secret.
      ```sh
      duploctl secret update <secret-name> --remove /SecretData/ExistingKey1 --remove /SecretData/ExistingKey2
      ```

    Example: Update a secret by specifying key-value pairs as literals.
      ```sh
      duploctl secret update <secret-name> --from-literal Key1="Val1" --from-literal Key2="Val2"
      ```

    Example: Update a secret from a file.
      ```sh
      duploctl secret update <secret-name> --from-file secret.txt
      ```

    Example: Adds labels and annotations to an existing Secret resource.
      Since annotations and labels do have dots and tildes, there is some special syntax here.
      ```sh
      duploctl secret update <secret-name> --add /SecretLabels/my.label~0/foo NewLabelVal --add SecretAnnotations.NewAnnotation AnnotationVal
      ```

    Args:
      name: Name of the secret. Required if `body` is not provided.
      body: The complete secret resource definition.
      data: Data to merge into the secret.
      patches: A list of JSON patches as args to apply to the service.
        The options are `--add`, `--remove`, `--replace`, `--move`, and `--copy`.
        Then followed by `<path>` and `<value>` for `--add`, `--replace`, and `--test`.
      dryrun: If True, return the modified secret without applying changes.

    Returns:
      message: The updated secret or a success message.

    Raises:
      DuploError: If the secret update fails.
    """
    if data:
      if not name:
        raise DuploError("Name is required when body is not provided")
      body = self.find(name)
      body.setdefault('SecretData', {}).update(data or {})
    return body if dryrun else super().update(name=name, body=body, patches=patches)

  @Command()
  def find(self,
           name: args.NAME) -> dict:
    """Find a Secret.

    Retrieve details of a specific kubernetes Secret by name

    Usage: cli usage
      ```sh
      duploctl secret find <name>
      ```

    Args:
      name: The name of the secret to find.

    Returns:
      message: The resource content or success message.

    Raises:
      DuploError: Secret not found.
    """
    try:
      response = self.duplo.get(self.endpoint(name))
    except DuploError as e:
      raise DuploError(f"Failed to find secret '{name}': {str(e)}")
    return response.json()

  @Command()
  def delete(self,
             name: args.NAME) -> dict:
    """Delete Secret

    Deletes the specified Secret by name.

    Usage: cli
      ```sh
      duploctl secret delete <name>
      ```

    Args:
      name: The name of a Secret to delete.

    Returns:
      message: Returns a success message if deleted successfully; otherwise, an error.
    """
    super().delete(name)
    return {
      "message": f"Successfully deleted secret '{name}'"
    }
