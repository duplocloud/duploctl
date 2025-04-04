from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Resource, Command
import duplocloud.args as args

@Resource("ingress")
class DuploIngress(DuploTenantResourceV3):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "k8s/ingress")

  def name_from_body(self, body):
    return body["name"]

  @Command()
  def create(self, body: args.BODY) -> dict:
    """Create an Ingress.
    Usage: CLI Usage
      ```sh
      duploctl ingress create -f 'ingress.yaml'
      ```
      Contents of the `ingress.yaml` file
      ```yaml
      --8<-- "src/tests/data/ingress.yaml"
      ```
    Example: One liner example
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/ingress.yaml"
      \"\"\" | duploctl ingress create -f -
      ```
    Args:
      body: The resource to create.
    Returns: 
      dict: The created resource or success message.
    """
    name = self.name_from_body(body)
    response = self.duplo.post(self.endpoint(), body)
    return {
      "message": f"Successfully Created an Ingress '{name}'",
      "data": response.json()
    }

  @Command()
  def update(self, body: args.BODY) -> dict:
    """Update an Ingress.
    Usage: CLI Usage
      ```sh
      duploctl ingress update -f 'ingress.yaml'
      ```
      Contents of the `ingress.yaml` file
      ```yaml
      --8<-- "src/tests/data/ingress.yaml"
      ```
    Example: One liner example
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/ingress.yaml"
      \"\"\" | duploctl ingress update -f -
      ```
    Args:
      body: The resource to update.
    Returns: 
      dict: The updated resource or success message.
    """
    name = self.name_from_body(body)
    response = self.duplo.put(self.endpoint(name), body)
    return {
      "message": f"Successfully Updated an Ingress '{name}'",
      "data": response.json()
    }
