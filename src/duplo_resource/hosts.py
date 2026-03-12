from duplocloud.controller import DuploCtl
from duplocloud.resource import DuploResourceV2
from duplocloud.errors import (
  DuploError, DuploFailedResource, DuploStillWaiting, DuploConnectionError
)
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("hosts", scope="tenant")
class DuploHosts(DuploResourceV2):
  """Manage Duplo Hosts
  
  Duplo hosts are virtual machines that run your services within a tenant. You can perform
  lifecycle operations like creating, deleting, starting, stopping and rebooting hosts.
  Hosts can be created with specific configurations like instance type, AMI, and other
  parameters.

  See more details at: https://docs.duplocloud.com/docs/welcome-to-duplocloud/application-focussed-interface/duplocloud-common-components/hosts
  """
  
  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)
    self.paths = {
      "list": "GetNativeHosts"
    }
  
  @Command()
  def find(self,
           name: args.NAME) -> dict:
    """Find a Host by name.

    Usage: CLI Usage
      ```sh
      duploctl hosts find <name>
      ```

    Args:
      name: The friendly name of the host to find.

    Returns:
      resource: The host object.

    Raises:
      DuploError: If the host could not be found.
    """
    prefix = f"duploservices-{self.tenant['AccountName']}-"
    search = name if name.startswith(prefix) else f"{prefix}{name}"
    try:
      return [h for h in self.list()
              if h.get("FriendlyName") and self.name_from_body(h) == search][0]
    except IndexError:
      raise DuploError(f"Host '{name}' not found", 404)

  @Command()
  def apply(self,
            body: args.BODY) -> dict:
    """Apply a Host.

    Create a host if it does not already exist.

    Usage: CLI Usage
      ```sh
      duploctl hosts apply -f 'hosts.yaml'
      ```

    Args:
      body: The host configuration.

    Returns:
      message: A success message or existing host.
    """
    name = body.get("FriendlyName", "")
    try:
      host = self.find(name)
      return {"message": f"Host '{name}' already exists", "data": host}
    except DuploConnectionError:
      raise
    except DuploError as e:
      if e.code != 404:
        raise
      return self.create(body)

  @Command(model="NativeHostRequest")
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

    Example: Create and Wait
      Supports global `--wait` flag to hold the terminal till the host is fully created and running.
      ```sh
      duploctl hosts create -f hosts.yaml --wait
      ```

    Args:
      body: The host configuration including instance type, AMI, and other parameters.

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
    res = self.client.post(self.endpoint("CreateNativeHost"), body)
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

    Example: Delete and Wait
      Supports global `--wait` flag to hold the terminal till the host is fully deleted.
      ```sh
      duploctl hosts delete myhost --wait
      ```

    Args:
      name: The name of the host to delete.

    Returns:
      message: Success message confirming the host deletion.

    Raises:
      DuploError: If the host does not exist or cannot be deleted.
      DuploFailedResource: If the deletion process fails.
    """
    host = self.find(name)
    inst_id = host["InstanceId"]
    res = self.client.post(self.endpoint(f"TerminateNativeHost/{inst_id}"), host)
    def wait_check():
      try:
        h = self.find(name)
      except DuploError as e:
        if e.code == 404:
          return None  # gone — done
        raise DuploStillWaiting(f"Host '{name}' is waiting for termination")
      if h.get("Status") in ("terminated", "shutting-down"):
        return None  # effectively gone
      if h.get("Status") == "running":
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

    Example: Stop and Wait
      Supports global `--wait` flag to hold the terminal till the host is fully stopped.
      ```sh
      duploctl hosts stop myhost --wait
      ```

    Args:
      name: The name of the host to stop.

    Returns:
      message: Success message confirming the host has been stopped.

    Raises:
      DuploError: If the host does not exist or cannot be stopped.
      DuploFailedResource: If the stop process fails.
    """
    host = self.find(name)
    inst_id = host["InstanceId"]
    res = self.client.post(self.endpoint(f"stopNativeHost/{inst_id}"), host)
    def wait_check():
      h = self.find(name)
      if h["Status"] == "running":
        raise DuploStillWaiting(f"Host '{name}' is waiting to begin stopping")
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

    Example: Start and Wait
      Supports global `--wait` flag to hold the terminal till the host is fully started.
      ```sh
      duploctl hosts start myhost --wait
      ```

    Args:
      name: The name of the host to start.
    
    Returns:
      message: Success message confirming the host has been started.

    Raises:
      DuploError: If the host does not exist or cannot be started.
      DuploFailedResource: If the start process fails.
    """
    host = self.find(name)
    inst_id = host["InstanceId"]
    res = self.client.post(self.endpoint(f"startNativeHost/{inst_id}"), host)
    def wait_check():
      h = self.find(name)
      if h["Status"] == "stopped":
        raise DuploStillWaiting(f"Host '{name}' is waiting to begin starting")
      if h["Status"] != "running":
        if h["Status"] != "pending":
          raise DuploFailedResource(f"Host '{name}' failed to start.")
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
    res = self.client.post(self.endpoint(f"RebootNativeHost/{inst_id}"), host)
    return {
      "message": f"Successfully rebooted host '{name}'",
      "data": res.json()
    }
    
  def name_from_body(self, body):
    name = body.get("FriendlyName")
    if name is None:
      return None
    prefix = f"duploservices-{self.tenant['AccountName']}"
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
