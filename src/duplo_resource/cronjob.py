from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("cronjob")
class DuploCronJob(DuploTenantResourceV3):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "k8s/cronJob")

  @Command()
  def update_image(self, 
                   name: args.NAME, 
                   image: args.IMAGE):
    """Update the image of a cronjob.
    
    Args:
      name (str): The name of the cronjob to update.
      image (str): The new image to use for the cronjob.
    """
    cronjob = self.find(name)
    cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["image"] = image
    self.update(cronjob)
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
    cronjob = self.find(name)
    cronjob["spec"]["schedule"] = cronschedule
    self.update(cronjob)
    return {"message": f"Successfully updated cron-schedule for cronjob '{name}'"}
  
  def name_from_body(self, body):
    return body["metadata"]["name"]
