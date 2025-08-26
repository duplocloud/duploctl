from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV2
from duplocloud.errors import DuploError, DuploFailedResource, DuploStillWaiting
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("hosts")
class DuploHosts(DuploTenantResourceV2):
  """Manage Duplo Hosts
  
  Duplo hosts are virtual machines that run your services within a tenant. You can perform
  lifecycle operations like creating, deleting, starting, stopping and rebooting hosts.
  Hosts can be created with specific configurations like instance type, AMI, and other
  parameters.

  See more details at: https://docs.duplocloud.com/docs/welcome-to-duplocloud/application-focussed-interface/duplocloud-common-components/hosts
  """
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self.paths = {
      "list": "GetNativeHosts"
    }
  
  @Command()
  def create(self,
             body: args.BODY) -> dict:
    """Create a Host resource.

    Creates a new host in the tenant with the specified configuration.

    Usage: CLI Usage
      ```sh
      duploctl hosts create -f 'hosts.yaml'
      ```
      Contents of the `hosts.yaml` file
      ```yaml
      --8<-- "src/tests/data/hosts.yaml"
      ```

    Example: Create a host using a one-liner
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/hosts.yaml"
      \"\"\" | duploctl hosts create -f -
      ```
    
    Args:
      body: The host configuration including instance type, AMI, and other parameters.
      wait: Whether to wait for the host to be fully created and running.

    Returns: 
      message: Success message and the instance ID of the created host.

    Raises:
      DuploError: If the host could not be created or the configuration is invalid.
      DuploFailedResource: If the host creation process fails.
    """
    def wait_check():
      name = self.name_from_body(body)
      h = self.find(name)
      if h["Status"] != "running":
        if h["Status"] != "pending":
          raise DuploFailedResource(f"Host '{name}' failed to create.")
        raise DuploStillWaiting(f"Host '{name}' is waiting")
    # let's get started
    if body.get("ImageId", None) is None:
      body["ImageId"] = self.discover_image(body.get("AgentPlatform", 0))
    res = self.duplo.post(self.endpoint("CreateNativeHost"), body)
    if self.duplo.wait:
      self.wait(wait_check)
    return {
      "message": f"Successfully created host '{body['FriendlyName']}'",
      "id": res.json()
    }
  
  @Command()
  def delete(self,
             name: args.NAME) -> dict:
    """Delete a host.
    
    Terminates a host by its name. This operation is irreversible and will
    destroy all data on the instance.

    Usage: CLI Usage
      ```sh
      duploctl hosts delete <name>
      ```
    
    Args:
      name: The name of the host to delete.
      wait: Whether to wait for the host to be fully terminated.

    Returns:
      message: Success message confirming the host deletion.

    Raises:
      DuploError: If the host does not exist or cannot be deleted.
      DuploFailedResource: If the deletion process fails.
    """
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
        raise DuploStillWaiting(f"Host '{name}' is waiting for termination")
    if self.duplo.wait:
      self.wait(wait_check, 500)
    return {
      "message": f"Successfully deleted host '{name}'",
      "data": res.json()
    }
  
  @Command()
  def stop(self,
           name: args.NAME) -> dict:
    """Stop a host.
    
    Stops a running host. The instance can be restarted later using the start
    command. Stopped instances do not incur compute charges but still incur storage costs.

    Usage: CLI Usage
      ```sh
      duploctl hosts stop <name>
      ```
    
    Args:
      name: The name of the host to stop.
      wait: Whether to wait for the host to reach stopped state.

    Returns:
      message: Success message confirming the host has been stopped.

    Raises:
      DuploError: If the host does not exist or cannot be stopped.
      DuploFailedResource: If the stop process fails.
    """
    host = self.find(name)
    inst_id = host["InstanceId"]
    res = self.duplo.post(self.endpoint(f"stopNativeHost/{inst_id}"), host)
    def wait_check():
      h = self.find(name)
      if h["Status"] == "running":
        raise DuploError(f"Host '{name}' not ready", 404)
      if h["Status"] != "stopped":
        if h["Status"] != "stopping":
          raise DuploFailedResource(f"Host '{name}' failed to stop.")
        raise DuploStillWaiting(f"Host '{name}' is waiting for status stopped")
    if self.duplo.wait:
      self.wait(wait_check, 500)
    return {
      "message": f"Successfully stopped host '{name}'",
      "data": res.json()
    }
  
  @Command()
  def start(self,
             name: args.NAME) -> dict:
    """Start a host.
    
    Starts a stopped host. The instance will retain its configuration and data
    from when it was stopped.

    Usage: CLI Usage
      ```sh
      duploctl hosts start <name>
      ```
    
    Args:
      name: The name of the host to start.
      wait: Whether to wait for the host to reach running state.
    
    Returns:
      message: Success message confirming the host has been started.

    Raises:
      DuploError: If the host does not exist or cannot be started.
      DuploFailedResource: If the start process fails.
    """
    host = self.find(name)
    inst_id = host["InstanceId"]
    res = self.duplo.post(self.endpoint(f"startNativeHost/{inst_id}"), host)
    def wait_check():
      h = self.find(name)
      if h["Status"] == "stopped":
        raise DuploError(f"Host '{name}' not ready", 404)
      if h["Status"] != "running":
        if h["Status"] != "pending":
          raise DuploFailedResource(f"Host '{name}' failed to stop.")
        raise DuploStillWaiting(f"Host '{name}' is waiting for status running")
    if self.duplo.wait:
      self.wait(wait_check, 500)
    return {
      "message": f"Successfully started host '{name}'",
      "data": res.json()
    }
  
  @Command()
  def reboot(self,
             name: args.NAME) -> dict:
    """Reboot a host.
    
    Performs a graceful reboot of a host. This is equivalent to an operating
    system reboot command. The instance ID and data are preserved.

    Usage: CLI Usage
      ```sh
      duploctl hosts reboot <name>
      ```

    Args:
      name: The name of the host to reboot.
    
    Returns:
      message: Success message confirming the reboot request.

    Raises:
      DuploError: If the host does not exist or cannot be rebooted.
    """
    host = self.find(name)
    inst_id = host["InstanceId"]
    res = self.duplo.post(self.endpoint(f"RebootNativeHost/{inst_id}"), host)
    return {
      "message": f"Successfully rebooted host '{name}'",
      "data": res.json()
    }
    
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
