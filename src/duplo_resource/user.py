from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.errors import DuploError

class DuploUser(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self.tenent_svc = duplo.service('tenant')
  
  def add_tenant(self, username, tenant):
    """Retrieve a list of all users in the Duplo system."""
    tenant_id = self.tenent_svc.find(tenant)["TenantId"]
    res = self.duplo.post("admin/UpdateUserAccess", {
      "Policy": { "IsReadOnly": None },
      "Username": username,
      "TenantId": tenant_id
    })
    # check http response is 204
    if res.status_code != 204:
      raise DuploError(f"Failed to add user '{username}' to tenant '{tenant}'", res["status_code"])
    else:
      return f"User '{username}' added to tenant '{tenant}'"

  def find(self, username):
    """Find a User by their username."""
    try:
      return [u for u in self.list() if u["Username"] == username][0]
    except IndexError:
      raise DuploError(f"User '{username}' not found", 404)
    
  def list(self):
    """Retrieve a list of all users in the Duplo system."""
    return self.duplo.get("admin/GetAllUserRoles")
