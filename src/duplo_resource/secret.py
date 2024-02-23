from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("secret")
class DuploSecret(DuploTenantResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self):
    """Retrieve a list of all Secrets in a tenant."""
    tenant_id = self.tenant["TenantId"]
    tenant_name = self.tenant["AccountName"]
    response = self.duplo.get(f"v3/subscriptions/{tenant_id}/k8s/secret")
    if (data := response.json()):
      return data
    else:
      raise DuploError(f"No secrets found in tenant '{tenant_name}'", 404)
  
  @Command()
  def find(self, 
           name: args.NAME):
    """Find a secret by name.
    
    Args:
      name (str): The name of the secret to find.
    Returns: 
      The secret object.
    Raises:
      DuploError: If the secret could not be found.
    """
    try:
      return [s for s in self.list() if s["SecretName"] == name][0]
    except IndexError:
      raise DuploError(f"Secret '{name}' not found", 404)

