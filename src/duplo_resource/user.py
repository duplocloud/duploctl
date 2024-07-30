from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("user")
class DuploUser(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self.tenent_svc = duplo.load('tenant')

  @Command()
  def list(self):
    """Retrieve a list of all users in the Duplo system."""
    response = self.duplo.get("admin/GetAllUserRoles")
    return response.json()
  
  @Command()
  def find(self, 
           name: args.NAME):
    """Find a User by their username."""
    try:
      return [u for u in self.list() if u["Username"] == name][0]
    except IndexError:
      raise DuploError(f"User '{name}' not found", 404)
  
  @Command()
  def add_user_to_tenant(self, 
                 name: args.NAME) -> dict:
    """Add User to Tenant
    
    Usage: CLI Usage
      ```sh
      duploctl user add_user_to_tenant <user> --tenant <tenant_name>
      ```

    Args:
      name: The name of the user to add to the tenant.
      tenant: The name of the tenant to add the user to.

    Returns:
      message: A message indicating the user was added to the tenant.
    """
    tenant_id = self.tenent_svc.find(self.duplo.tenant)["TenantId"]
    res = self.duplo.post("admin/UpdateUserAccess", {
      "Policy": { "IsReadOnly": None },
      "Username": name,
      "TenantId": tenant_id
    })
    # check http response is 204
    if res.status_code != 204:
      raise DuploError(f"Failed to add user '{name}' to tenant '{self.duplo.tenant}'", res["status_code"])
    else:
      return f"User '{name}' added to tenant '{self.duplo.tenant}'"
    
  @Command()
  def remove_user_from_tenant(self, 
                 name: args.NAME) -> dict:
    """Remove a User from a Tenant
    
    Usage: CLI Usage
      ```sh
      duploctl user remove_user_from_tenant <user> --tenant <tenant_name>
      ```

    Args:
      name: The name of the user to remove from the tenant.
      tenant: The name of the tenant to remove the user from.

    Returns:
      message: A message indicating the user was removed from the tenant.
    """
    tenant_id = self.tenent_svc.find(self.duplo.tenant)["TenantId"]
    res = self.duplo.post("admin/UpdateUserAccess", {
      "Policy": {},
      "Username": name,
      "TenantId": tenant_id,
      "State": "deleted"
    })

    # check http response is 204
    if res.status_code != 204:
      raise DuploError(f"Failed to remove user '{name}' from tenant '{self.duplo.tenant}'", res["status_code"])
    else:
      return f"User '{name}' removed from tenant '{self.duplo.tenant}'"
    
  @Command()
  def create(self, 
             body: args.BODY):
    """Create a new user.

    Usage: CLI Usage
      ```sh
      duploctl user create -f 'user.yaml'
      ```
      Contents of the `user.yaml` file
      ```yaml
      --8<-- "src/tests/data/user.yaml"
      ```
    
    Args:
      body: The user body. 

    Returns:
      message: A success message.
    """
    if 'State' not in body:
      body['State'] = 'added'
    response = self.duplo.post("admin/UpdateUserRole", body)
    return response.json()
  
  @Command()
  def delete(self, 
             name: args.NAME) -> dict:
    """Delete a User.
    
    Usage: CLI Usage
      ```sh
      duploctl user delete <name>
      ```
    
    Args:
      name: The name of the user to delete.
    
    Returns:
      message: A success message.
    """
    body = {
      "Username": name,
      "State": "deleted"
    }
    self.duplo.post("admin/UpdateUserRole", body)
    return {"message": name+ " deleted successfully"}
