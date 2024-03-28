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
  def create(self,
             body: args.BODY,
             wait: args.WAIT=False):
    """Create an ASG."""
    tenant_id = self.tenant["TenantId"]
    res = self.duplo.post(f"subscriptions/{tenant_id}/UpdateTenantAsgProfile", body)
    def wait_check():
      return self.find(body["FriendlyName"])
    if wait:
      self.wait(wait_check)
    return {
      "message": f"Successfully created asg '{body['FriendlyName']}'",
      "data": res.json()
    }
  
  @Command()
  def update(self,
             body: args.BODY):
    """Update an ASG."""
    tenant_id = self.tenant["TenantId"]
    res = self.duplo.post(f"subscriptions/{tenant_id}/UpdateTenantAsgProfile", body)
    return {
      "message": f"Successfully updated asg '{body['FriendlyName']}'",
      "data": res.json()
    }
  
  @Command()
  def delete(self,
             name: args.NAME):
    """Delete an ASG."""
    tenant_id = self.tenant["TenantId"]
    body = { 
      "FriendlyName": name,
      "State": "delete"
    }
    res = self.duplo.post(f"subscriptions/{tenant_id}/UpdateTenantAsgProfile", body)
    return {
      "message": f"Successfully deleted asg '{name}'",
      "data": res.json()
    }

  @Command()
  def scale(self,
            name: args.NAME,
            min: args.MIN=None,
            max: args.MAX=None):
    """Scale an ASG."""
    if not min and not max:
      raise DuploError("Must provide either min or max")
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
    return self.update(data)
  
  def name_from_body(self, body):
    return body["FriendlyName"]
