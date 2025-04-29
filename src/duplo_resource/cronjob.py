from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("cronjob")
class DuploCronJob(DuploTenantResourceV3):
  """
  Duplo CronJob are scheduled jobs that run containers in a Kubernetes cluster.
  """

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

    # Set IsAnyHostAllowed
    self._set_is_any_host_allowed(cronjob)

    cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["image"] = image
    self.update(name=name, body=cronjob)
    return {"message": f"Successfully updated image for cronjob '{name}'"}

  @Command()
  def update_schedule(self,
                      name: args.NAME,
                      cronschedule: args.CRONSCHEDULE) -> dict:
    """Update the schedule of a cronjob.

    Args:
      name: The name of the cronjob to update.
      cronschedule: The new schedule to use for the cronjob.
    Returns:
      message: A success message.
    """
    cronjob = self.find(name)

    # Set IsAnyHostAllowed
    self._set_is_any_host_allowed(cronjob)

    cronjob["spec"]["schedule"] = cronschedule
    self.update(name=name, body=cronjob)
    return {"message": f"Successfully updated cron-schedule for cronjob '{name}'"}

  def _set_is_any_host_allowed(self, cronjob: dict) -> None:
    """Helper method to set the 'IsAnyHostAllowed' field based on cronjob annotations."""
    # Check if the annotation "duplocloud.net/is-any-host-allowed" exists and set `IsAnyHostAllowed`
    annotations = cronjob.get("metadata", {}).get("annotations", {})
    is_any_host_allowed = annotations.get("duplocloud.net/is-any-host-allowed")

    if is_any_host_allowed == "true":
      cronjob["IsAnyHostAllowed"] = True
    else:
      cronjob["IsAnyHostAllowed"] = False