from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV2
from duplocloud.errors import DuploError, DuploFailedResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("hosts")
class DuploHosts(DuploTenantResourceV2):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self.paths = {
      "list": "GetNativeHosts"
    }
  
  @Command()
  def create(self,
             body: args.BODY,
             wait: args.WAIT=False):
    """Create a host."""
    def wait_check():
      name = self.name_from_body(body)
      h = self.find(name)
      if h["Status"] != "running":
        if h["Status"] != "pending":
          raise DuploFailedResource(f"Host '{name}' failed to create.")
        raise DuploError(f"Host '{name}' not ready", 404)
    # let's get started
    if body.get("ImageId", None) is None:
      body["ImageId"] = self.discover_image(body.get("AgentPlatform", 0))
    res = self.duplo.post(self.endpoint("CreateNativeHost"), body)
    if wait:
      self.wait(wait_check)
    return {
      "message": f"Successfully created host '{body['FriendlyName']}'",
      "id": res.json()
    }
  
  @Command()
  def delete(self,
             name: args.NAME,
             wait: args.WAIT=False):
    """Delete a host."""
    host = self.find(name)
    inst_id = host["InstanceId"]
    res = self.duplo.post(self.endpoint(f"TerminateNativeHost/{inst_id}"), host)
    def wait_check():
      h = None 
      try:
        h = self.find(name)
      except DuploError as e:
        if e.code == 404:
          return None # if 404 then it's gone so finish waiting
        else:
          raise DuploFailedResource(f"Host '{name}' failed to delete.")
      if h["Status"] == "shutting-down" or h["Status"] == "running":
        raise DuploError(f"Host '{name}' not terminated", 404)
    if wait:
      self.wait(wait_check, 500)
    return {
      "message": f"Successfully deleted host '{name}'",
      "data": res.json()
    }
    
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
