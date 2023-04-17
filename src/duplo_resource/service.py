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
    """Find a service by name.
    
    Args:
      service_name (str): The name of the service to find.
    Returns: 
      The service object.
    Raises:
      DuploError: If the service could not be found.
    """
    try:
      return [s for s in self.list() if s["Name"] == service_name][0]
    except IndexError:
      raise DuploError(f"Service '{service_name}' not found", 404)

  def update_image(self, service_name, image):
    """Update the image of a service.
    
    Args:
      service_name (str): The name of the service to update.
      image (str): The new image to use for the service.
    """
    tenant_id = self.get_tenant()["TenantId"]
    service = self.find(service_name)
    allocation_tags = service["Template"]["AllocationTags"]
    data = {
      "Name": service_name,
      "Image": image,
      "AllocationTags": allocation_tags
    }
    return self.duplo.post(f"subscriptions/{tenant_id}/ReplicationControllerChange", data)
  
  def restart(self, service_name):
    """Restart a service.
    
    Args:
      service_name (str): The name of the service to restart.
    Returns: 
      A success message if the service was restarted successfully.
    Raises:
      DuploError: If the service could not be restarted.
    """
    tenant_id = self.get_tenant()["TenantId"]
    res = self.duplo.post(f"subscriptions/{tenant_id}/ReplicationControllerReboot/{service_name}")
    if res.status_code == 200:
      return f"Successfully restarted service '{service_name}'"
    else:
      raise DuploError(f"Failed to restart service '{service_name}'")
  