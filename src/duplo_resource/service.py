from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.errors import DuploError

class DuploService(DuploResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self.tenent_svc = duplo.service('tenant')
  
  def list(self):
    """Retrieve a list of all services in a tenant."""
    tenant_id = self.get_tenant()["TenantId"]
    return self.duplo.get(f"subscriptions/{tenant_id}/GetReplicationControllers")
  
  def find(self, service_name):
    """Find a service by name."""
    try:
      return [s for s in self.list() if s["Name"] == service_name][0]
    except IndexError:
      raise DuploError(f"Service '{service_name}' not found", 404)

  def update_image(self, service_name, image):
    tenant_id = self.get_tenant()["TenantId"]
    service = self.find(service_name)
    allocation_tags = service["Template"]["AllocationTags"]
    data = {
      "Name": service_name,
      "Image": image,
      "AllocationTags": allocation_tags
    }
    return self.duplo.post(f"subscriptions/{tenant_id}/ReplicationControllerChange", data)