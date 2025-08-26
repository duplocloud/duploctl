from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV2
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("asg")
class DuploAsg(DuploTenantResourceV2):
  """Manage Duplo ASGs

  Duplo ASGs (Auto Scaling Groups) manage the number of hosts within a tenant, enabling automatic scaling of instances based on demand.

  See more details at: https://docs.duplocloud.com/docs/overview/use-cases/hosts-vms/auto-scaling/auto-scaling-groups
  """
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self) -> list:
    """List all ASGs.

    Retrieve the list of all Auto Scaling Groups in the tenant.

    Usage: CLI Usage
      ```sh
      duploctl asg list
      ```

    Returns:
      list: A list of all ASGs with their configurations.
    """
    tenant_id = self.tenant["TenantId"]
    response = self.duplo.get(f"subscriptions/{tenant_id}/GetTenantAsgProfiles")
    return response.json()

  @Command()
  def find(self, 
           name: args.NAME):
    """Find an ASG by name.

    Retrieve details of a specific Auto Scaling Group by its name.

    Usage: CLI Usage
      ```sh
      duploctl asg find <name>
      ```

    Args:
      name: The name of the ASG to find.

    Returns:
      dict: The ASG configuration including capacity, instance types, and other settings.

    Raises:
      DuploError: If the ASG with the specified name could not be found.
    """
    try:
      return [s for s in self.list() if s["FriendlyName"] == name][0]
    except IndexError:
      raise DuploError(f"ASG Profile '{name}' not found", 404)
    
  @Command()
  def create(self,
             body: args.BODY) -> dict:
    """Create an ASG.

    Creates a new Auto Scaling Group with the specified configuration. The ASG will manage
    EC2 instances based on the defined capacity settings and scaling policies.
    
    Usage: CLI Usage
      ```sh
      duploctl hosts create -f 'asg.yaml'
      ```
      Contents of the `asg.yaml` file
      ```yaml
      --8<-- "src/tests/data/asg.yaml"
      ```

    Example: Create an ASG using a one-liner.
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/asg.yaml"
      \"\"\" | duploctl asg create -f -
      ```

    Args:
      body: The complete ASG configuration including instance type, capacity settings,
            and other parameters.
      wait: Whether to wait for the ASG to be fully created and ready.

    Returns:
      message: Success message and the created ASG configuration.

    Raises:
      DuploError: If the ASG could not be created due to invalid configuration or API errors.
    """
    tenant_id = self.tenant["TenantId"]
    name = self.name_from_body(body)
    if body.get("ImageId", None) is None:
      body["ImageId"] = self.discover_image(body.get("AgentPlatform", 0))
    res = self.duplo.post(f"subscriptions/{tenant_id}/UpdateTenantAsgProfile", body)
    def wait_check():
      return self.find(name)
    if self.duplo.wait:
      self.wait(wait_check)
    return {
      "message": f"Successfully created asg '{body['FriendlyName']}'",
      "data": res.json()
    }
  
  @Command()
  def update(self,
             body: args.BODY) -> dict:
    """Update an ASG.

    Update an existing Auto Scaling Group's configuration. This can include changes to
    capacity settings, instance types, scaling policies, and other parameters.

    Usage: CLI Usage
      ```sh
      duploctl asg update -f <file>
      ```
    
    Args:
      body: The updated ASG configuration. Must include the FriendlyName of the existing ASG.

    Returns:
      message: Success message and the updated ASG configuration.

    Raises:
      DuploError: If the ASG could not be updated due to invalid configuration or API errors.
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
    """Delete an ASG.

    Delete an Auto Scaling Group by its name. This will terminate all instances
    managed by the ASG and remove the ASG configuration.

    Usage: CLI Usage
      ```sh
      duploctl asg delete <name>
      ```

    Args:
      name: The name of the ASG to delete.

    Returns:
      message: Success message confirming the ASG deletion.

    Raises:
      DuploError: If the ASG could not be deleted or does not exist.
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

    Modify the capacity limits of an Auto Scaling Group. You can set new minimum and/or
    maximum instance counts. The ASG will automatically adjust the number of running
    instances to stay within these new bounds.

    Usage: CLI Usage
      ```sh
      duploctl asg scale -n <name> [-m <min>] [-M <max>]
      ```
    
    Args:
      name: The  name of the ASG to scale.
      min: The new minimum number of instances the ASG should maintain. Use -m flag to set.
      max: The new maximum number of instances the ASG can scale to. Use -M flag to set.

    Returns:
      message: Success message with the new scaling configuration.

    Raises:
      DuploError: If neither min nor max is provided, or if the scaling operation fails.
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
