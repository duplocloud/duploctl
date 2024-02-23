from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("asg")
class DuploAsg(DuploTenantResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self):
    """Retrieve a list of all services in a tenant."""
    tenant_id = self.tenant["TenantId"]
    response = self.duplo.get(f"subscriptions/{tenant_id}/GetTenantAsgProfiles")
    return response.json()

  @Command()
  def find(self, 
           name: args.NAME):
    """Find an asg by name.
    
    Args:
      name (str): The name of the asg to find.
    Returns: 
      The service object.
    Raises:
      DuploError: If the asg could not be found.
    """
    try:
      return [s for s in self.list() if s["FriendlyName"] == name][0]
    except IndexError:
      raise DuploError(f"ASG Profile '{name}' not found", 404)

  @Command()
  def scale(self,
            name: args.NAME,
            min: args.MIN=None,
            max: args.MAX=None):
    """Scale an ASG."""
    if not min and not max:
      raise DuploError("Must provide either min or max")
    tenant_id = self.tenant["TenantId"]
    asg = self.find(name)
    data = {
      "FriendlyName": name,
      "DesiredCapacity": asg.get("MinSize", None),
      "MinSize": asg.get("MinSize", None),# this really is a string unlike the other two? 
      "MaxSize": asg.get("MaxSize", None),
    }
    if min:
      data["MinSize"] = str(min)
    if max:
      data["MaxSize"] = max
    res = self.duplo.post(f"subscriptions/{tenant_id}/UpdateTenantAsgProfile", data)
    return {
      "message": f"Successfully updated asg '{name}'",
      "data": res.json()
    }
  