from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
from json import dumps, loads
import duplocloud.args as args

@Resource("service")
class DuploService(DuploTenantResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self):
    """Retrieve a list of all services in a tenant."""
    tenant_id = self.tenant["TenantId"]
    response = self.duplo.get(f"subscriptions/{tenant_id}/GetReplicationControllers")
    return response.json()
  
  @Command()
  def find(self, 
           name: args.NAME):
    """Find a service by name.
    
    Args:
      name (str): The name of the service to find.
    Returns: 
      The service object.
    Raises:
      DuploError: If the service could not be found.
    """
    try:
      return [s for s in self.list() if s["Name"] == name][0]
    except IndexError:
      raise DuploError(f"Service '{name}' not found", 404)

  @Command()
  def update_replicas(self, name: args.NAME,
                      replica: args.REPLICAS):
    """Update number of replicas for a service.

    Args:
        name (str): The name of the service to update.
        replica (str): Number of replicas to set for service.
    """
    try:
      tenant_id = self.tenant["TenantId"]
      service = self.find(name)
      data = {
        "Name": name,
        "Replicas": replica,
        "AllocationTags": service["Template"].get("AllocationTags", "")
      }
      response = self.duplo.post(f"subscriptions/{tenant_id}/ReplicationControllerChange", data)
      if response.json() is None:
        return {"message": f"Successfully updated replicas for service '{name}'"} 
    except IndexError:
      raise DuploError(f"Service '{name}' not found to set replica count.", 404)
  
  @Command()
  def update_image(self, 
                   name: args.NAME, 
                   image: args.IMAGE):
    """Update the image of a service.
    
    Args:
      name (str): The name of the service to update.
      image (str): The new image to use for the service.
    """
    tenant_id = self.tenant["TenantId"]
    service = self.find(name)
    current_image =  None
    for container in service["Template"]["Containers"]:
        if container["Name"] == name:
            current_image = container["Image"]
    if(current_image == image):
      self.duplo.post(f"subscriptions/{tenant_id}/ReplicationControllerReboot/{name}")
    else:
      data = {
        "Name": name,
        "Image": image,
        "AllocationTags": service["Template"].get("AllocationTags", "")
      }
      self.duplo.post(f"subscriptions/{tenant_id}/ReplicationControllerChange", data)
    return {"message": f"Successfully updated image for service '{name}'"}
 
  @Command()
  def update_env(self, 
                 name: args.NAME,
                 setvar: args.SETVAR, 
                 strategy: args.STRATEGY,
                 deletevar: args.DELETEVAR):
    """Update the environment variables of a service.

    Args:
      name (str): The name of the service to update.
      setvar/-V (list): A list of key value pairs to set as environment variables.
      strategy/strat (str): The merge strategy to use for env vars. Valid options are "merge" or "replace".  Default is merge.
      deletevar/-D (list): A list of keys to delete from the environment variables.
    """
    tenant_id = self.tenant["TenantId"]
    service = self.find(name)
    currentDockerconfig = loads(service["Template"]["OtherDockerConfig"])
    currentEnv = currentDockerconfig.get("Env", [])
    newEnv = []
    if setvar is not None:
      newEnv = [{"Name": i[0], "Value": i[1]} for i in setvar]
    if strategy == 'merge':
      d = {d['Name']: d for d in currentEnv + newEnv}
      mergedvars = list(d.values())
      currentDockerconfig['Env'] = mergedvars
    else:
      currentDockerconfig['Env'] = newEnv
    if deletevar is not None:
      for key in deletevar:
        currentDockerconfig['Env'] = [d for d in currentDockerconfig['Env'] if d['Name'] != key]
    payload = {
      "Name": name,
      "OtherDockerConfig": dumps(currentDockerconfig),
      "allocationTags": service["Template"].get("AllocationTags", "")
    }
    self.duplo.post(f"subscriptions/{tenant_id}/ReplicationControllerChange", payload)
    return {"message": "Successfully updated environment variables for services"}
    
  
  @Command()
  def bulk_update_image(self, 
                  serviceimage: args.SERVICEIMAGE):
    """Update multiple services.
    
    Args:
      serviceimage/-S (string): takes n sets of two arguments, service name and image name. e.g -S service1 image1:tag -S service2 image2:tag
    """
    tenant_id = self.tenant["TenantId"]
    payload = []
    for i in serviceimage:
      servicepair = dict([i])
      for name, image in servicepair.items():
        payloaditem = {}
        service = self.find(name)
        allocation_tags = service["Template"]["AllocationTags"]
        payloaditem["Name"] = name
        payloaditem["Image"] = image
        payloaditem["AllocationTags"] = allocation_tags
        payload.append(payloaditem)
    self.duplo.post(f"subscriptions/{tenant_id}/ReplicationControllerBulkChangeAll", payload)
    return {"message": "Successfully updated images for services"}

  @Command()
  def restart(self, 
              name: args.NAME):
    """Restart a service.
    
    Args:
      name (str): The name of the service to restart.
    Returns: 
      A success message if the service was restarted successfully.
    Raises:
      DuploError: If the service could not be restarted.
    """
    tenant_id = self.tenant["TenantId"]
    self.duplo.post(f"subscriptions/{tenant_id}/ReplicationControllerReboot/{name}")
    return {"message": f"Successfully restarted service '{name}'"}
  
  @Command()
  def stop(self, 
           name: args.NAME):
    """Stop a service.
    
    Args:
      name (str): The name of the service to stop.
    Returns: 
      A success message if the service was stopped successfully.
    Raises:
      DuploError: If the service could not be stopped.
    """
    tenant_id = self.tenant["TenantId"]
    self.duplo.post(f"subscriptions/{tenant_id}/ReplicationControllerStop/{name}")
    return {"message": f"Successfully stopped service '{name}'"}
  
  @Command()
  def start(self, 
            name: args.NAME):
    """Start a service.
    
    Args:
      name (str): The name of the service to start.
    Returns: 
      A success message if the service was started successfully.
    Raises:
      DuploError: If the service could not be started.
    """
    tenant_id = self.tenant["TenantId"]
    self.duplo.post(f"subscriptions/{tenant_id}/ReplicationControllerstart/{name}")
    return {"message": f"Successfully started service '{name}'"}
