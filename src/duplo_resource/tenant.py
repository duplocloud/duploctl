from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.errors import DuploError

class DuploTenant(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  def list(self):
    """Retrieve a list of all tenants in the Duplo system."""
    return self.duplo.get("adminproxy/GetTenantNames")

  def find(self, tenant_name):
    """Find a tenant by name."""
    try:
      return [t for t in self.list() if t["AccountName"] == tenant_name][0]
    except IndexError:
      raise DuploError(f"Tenant '{tenant_name}' not found", 404)
