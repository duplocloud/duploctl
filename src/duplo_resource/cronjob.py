from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("cronjob")
class DuploCronJob(DuploTenantResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self):
    """Retrieve a list of all services in a tenant."""
    tenant_id = self.tenant["TenantId"]
    return self.duplo.get(f"v3/subscriptions/{tenant_id}/k8s/cronJob")
  
  @Command()
  def find(self, 
           name: args.NAME):
    """Find a cronjob by name.
    
    Args:
      name (str): The name of the cronjob to find.
    Returns: 
      The cronjob object.
    Raises:
      DuploError: If the cronjob could not be found.
    """
    tenant_id = self.tenant["TenantId"]
    return self.duplo.get(f"v3/subscriptions/{tenant_id}/k8s/cronJob/{name}")

  @Command()
  def update_image(self, 
                   name: args.NAME, 
                   image: args.IMAGE):
    """Update the image of a cronjob.
    
    Args:
      name (str): The name of the cronjob to update.
      image (str): The new image to use for the cronjob.
    """
    tenant_id = self.tenant["TenantId"]
    cronjob = self.find(name)
    cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["image"] = image
    self.duplo.put(f"v3/subscriptions/{tenant_id}/k8s/cronJob/{name}", cronjob)
    return {"message": f"Successfully updated image for cronjob '{name}'"}
  
  @Command()
  def update_schedule(self, 
                      name: args.NAME, 
                      cronschedule: args.CRONSCHEDULE):
    """Update the schedule of a cronjob.
    
    Args:
      name (str): The name of the cronjob to update.
      schedule (str): The new schedule to use for the cronjob.
    """
    tenant_id = self.tenant["TenantId"]
    cronjob = self.find(name)
    cronjob["spec"]["schedule"] = cronschedule
    self.duplo.put(f"v3/subscriptions/{tenant_id}/k8s/cronJob/{name}", cronjob)
    return {"message": f"Successfully updated cron-schedule for cronjob '{name}'"}
  
  
