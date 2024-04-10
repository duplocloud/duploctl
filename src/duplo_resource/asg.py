from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV2
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("asg")
class DuploAsg(DuploTenantResourceV2):
  
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
    name = self.name_from_body(body)
    if body.get("ImageId", None) is None:
      body["ImageId"] = self.discover_image(body.get("AgentPlatform", 0))
    res = self.duplo.post(f"subscriptions/{tenant_id}/UpdateTenantAsgProfile", body)
    def wait_check():
      return self.find(name)
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
    prefix = f"duploservices-{self.duplo.tenant}"
    name =  body["FriendlyName"]
    if not name.startswith(prefix):
      name = f"{prefix}-{name}"
    return name

  def discover_image(self, agent, arch="amd64"):
    imgs = self.tenant_svc.host_images(self.duplo.tenant)
    try:
      img = [i for i in imgs if i["Agent"] == agent and i["Arch"] == arch][0]
      return img.get("ImageId")
    except IndexError:
      raise DuploError(f"Image for agent '{agent}' not found", 404)
