from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV2
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("asg")
class DuploAsg(DuploTenantResourceV2):
  """Manage Duplo ASGs

  Duplo ASGs are Auto Scaling Groups that manage the number of hosts within a tenant.
  """
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self) -> list:
    """List all ASGs
    
    Usage: CLI Usage
      ```sh
      duploctl asg list
      ```
    Returns:
      list: A list of all ASGs.
    """
    tenant_id = self.tenant["TenantId"]
    response = self.duplo.get(f"subscriptions/{tenant_id}/GetTenantAsgProfiles")
    return response.json()

  @Command()
  def find(self, 
           name: args.NAME):
    """Find an asg by name.

    Usage: CLI Usage
      ```sh
      duploctl asg find <name>
      ```
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
             wait: args.WAIT=False) -> dict:
    """Create an ASG
    
    Usage: CLI Usage
      ```sh
      duploctl hosts create -f 'asg.yaml'
      ```
      Contents of the `asg.yaml` file
      ```yaml
      --8<-- "src/tests/data/asg.yaml"
      ```
    Example: One liner example
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/asg.yaml"
      \"\"\" | duploctl asg create -f -
      ```
    Args:
      body: The body of the request.
      wait: Whether to wait for the creation to complete.
    Returns:
      message: A message that the asg was successfully created.
    """
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
             body: args.BODY) -> dict:
    """Update an ASG.

    Usage: CLI Usage
      ```sh
      duploctl asg update -f <file>
      ```
    
    Args:
      body: The body of the request.

    Returns:
      message: A message that the asg was successfully updated
    """
    tenant_id = self.tenant["TenantId"]
    res = self.duplo.post(f"subscriptions/{tenant_id}/UpdateTenantAsgProfile", body)
    return {
      "message": f"Successfully updated asg '{body['FriendlyName']}'",
      "data": res.json()
    }
  
  @Command()
  def delete(self,
             name: args.NAME) -> dict:
    """Delete an ASG

    Usage: CLI Usage
      ```sh
      duploctl asg delete <name>
      ```
    
    Args:
      name: The name of the asg to delete.

    Returns:
      message: A message that the asg was successfully deleted.
    """
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
            max: args.MAX=None) -> dict:
    """Scale an ASG.
    
    Note: "-m" represents Minimum instances and "-M" represents Maximum instances.

    Usage: CLI Usage
      ```sh
      duploctl asg scale -n <name> [-m <min>] [-M <max>]
    
    Args:
      name: The name of the asg to scale.
      min: The minimum number of instances.
      max: The maximum number of instances.

    Returns:
      message: A messaget that the asg was successfully scaled.
    """
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
    prefix = f"duploservices-{self.tenant['AccountName']}"
    name =  body["FriendlyName"]
    if not name.startswith(prefix):
      name = f"{prefix}-{name}"
    return name

  def discover_image(self, agent, arch="amd64"):
    imgs = self.tenant_svc.host_images(self.tenant['AccountName'])
    try:
      img = [i for i in imgs if i["Agent"] == agent and i["Arch"] == arch][0]
      return img.get("ImageId")
    except IndexError:
      raise DuploError(f"Image for agent '{agent}' not found", 404)
