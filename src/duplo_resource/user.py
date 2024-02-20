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
                 name: args.NAME, 
                 tenant: args.TENANT):
    """Retrieve a list of all users in the Duplo system."""
    tenant_id = self.tenent_svc.find(tenant)["TenantId"]
    res = self.duplo.post("admin/UpdateUserAccess", {
      "Policy": { "IsReadOnly": None },
      "Username": name,
      "TenantId": tenant_id
    })
    # check http response is 204
    if res.status_code != 204:
      raise DuploError(f"Failed to add user '{name}' to tenant '{tenant}'", res["status_code"])
    else:
      return f"User '{name}' added to tenant '{tenant}'"
