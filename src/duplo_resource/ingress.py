from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.errors import DuploError
from duplocloud.commander import Resource, Command
import duplocloud.args as args

@Resource("ingress")
class DuploIngress(DuploTenantResourceV3):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "k8s/ingress")

  def name_from_body(self, body):
    return body["name"]

  @Command()
  def create(self,
             body: args.BODY) -> dict:
    """Create an Ingress resource.

    Creates a new Ingress resource with the specified metadata and data entries.

    Usage: CLI Usage
      ```sh
      duploctl ingress create -f ingress.yaml
      ```
      Contents of the `ingress.yaml` file
      ```yaml
      --8<-- "src/tests/data/ingress.yaml"
      ```

    Example: Create an Ingress using a one-liner.
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/ingress.yaml"
      \"\"\" | duploctl ingress create -f -
      ```

    Example: Create an Ingress using a file.
      ```sh
      duploctl ingress create -f ingress.yaml
      ```

    Args:
      body: The complete Ingress resource definition.

    Returns:
      message: The created resource or success message.

    Raises:
      DuploError: If the Ingress could not be created.
    """
    name = self.name_from_body(body)
    response = self.duplo.post(self.endpoint(), body)
    return {
      "message": f"Successfully Created an Ingress '{name}'",
      "data": response.json()
    }

  @Command()
  def update(self,
             name: args.NAME,
             body: args.BODY = None,
             patches: args.PATCHES = None) -> dict:
    """Update an Ingress resource.

    Update an exisitng Ingress resource with the specified metadata and data entries.

    Usage: CLI Usage
      ```sh
      duploctl ingress update -f ingress.yaml
      ```
      Contents of the `ingress.yaml` file
      ```yaml
      --8<-- "src/tests/data/ingress.yaml"
      ```

    Example: Update ingress using a one-liner.
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/ingress.yaml"
      \"\"\" | duploctl ingress update -f -
      ```

    Example: Update dnsPrefix for an ingress.
      ```sh
      duploctl ingress update <ingress-name> --replace lbConfig.dnsPrefix <value>
      ```

    Example: Update port of a rule for an ingress.
      ```sh
      duploctl ingress update <ingress-name> --replace rules/0.port <port>
      ```

    Args:
      name: The name of the Ingress resource to update. Required if `body` is not provided.\n
      body: The complete Ingress resource definition.\n
      patches: A list of JSON patches as args to apply to the service.
        The options are `--add`, `--remove`, `--replace`, `--move`, and `--copy`.
        Then followed by `<path>` and `<value>` for `--add`, `--replace`, and `--test`.

    Returns:
      message: The updated resource or success message.

    Raises:
      DuploError: If the Ingress could not be updated.
    """
    if (name is None and body is None):
      raise DuploError("No arguments provided to update ingress", 400)
    if name and body:
      if 'name' not in body or body['name'] != name:
        raise DuploError("Provided 'name' must match 'name' in the body.")
    if body is None:
      body = self.find(name)
    response = super().update(name=name, body=body, patches=patches)
    return {
      "message": f"Successfully Updated an Ingress '{name}'",
      "data": response
    }
