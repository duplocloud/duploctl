from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV2
from duplocloud.errors import DuploError, DuploFailedResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("hosts")
class DuploHosts(DuploTenantResourceV2):
  """Manage Duplo Hosts
  
  Duplo hosts are virtual machines that run your services. You can create, delete, start, stop, and reboot hosts.
  """
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self.paths = {
      "list": "GetNativeHosts"
    }
  
  @Command()
  def create(self,
             body: args.BODY,
             wait: args.WAIT=False) -> dict:
    """Create a Hosts resource.

    Usage: CLI Usage
      ```sh
      duploctl hosts create -f 'hosts.yaml'
      ```
      Contents of the `hosts.yaml` file
      ```yaml
      --8<-- "src/tests/data/hosts.yaml"
      ```

    Example: One liner example
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/hosts.yaml"
      \"\"\" | duploctl hosts create -f -
      ```
    
    Args:
      body: The resource to create.
      wait: Wait for the resource to be created.

    Returns: 
      message: Success message.

    Raises:
      DuploError: If the resource could not be created.
    """
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
             wait: args.WAIT=False) -> dict:
    """Delete a host.
    
    Deletes a host by name. If the host is running, it will be stopped before deletion.

    Usage: cli
      ```sh
      duploctl hosts delete <name>
      ```
    
    Args:
      name: The name of the host to delete.
      wait: Wait for the host to be deleted.

    Returns:
      message: A success message.
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
        raise DuploError(f"Host '{name}' not terminated", 404)
    if wait:
      self.wait(wait_check, 500)
    return {
      "message": f"Successfully deleted host '{name}'",
      "data": res.json()
    }
  
  @Command()
  def stop(self,
           name: args.NAME,
           wait: args.WAIT=False) -> dict:
    """Stop a host.
    
    Stops a host by name. If the host is already stopped, it will return a success message.

    Usage: cli
      ```sh
      duploctl hosts stop <name>
      ```
    
    Args:
      name: The name of the host to stop.
      wait: Wait for the host to stop.

    Returns:
      message: A success message.
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
        raise DuploError(f"Host '{name}' not ready", 404)
    if wait:
      self.wait(wait_check, 500)
    return {
      "message": f"Successfully stopped host '{name}'",
      "data": res.json()
    }
  
  @Command()
  def start(self,
             name: args.NAME,
             wait: args.WAIT=False) -> dict:
    """Start a host.
    
    Starts a host by name. If the host is already running, it will return a success message.

    Usage: cli
      ```sh
      duploctl hosts start <name>
      ```
    
    Args:
      name: The name of the host to start.
      wait: Wait for the host to start.
    
    Returns:
      message: A success message.
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
        raise DuploError(f"Host '{name}' not ready", 404)
    if wait:
      self.wait(wait_check, 500)
    return {
      "message": f"Successfully started host '{name}'",
      "data": res.json()
    }
  
  @Command()
  def reboot(self,
             name: args.NAME) -> dict:
    """Reboot a host
    
    Reboots a host by name.

    Usage: cli
      ```sh
      duploctl hosts reboot <name>
      ```

    Args:
      name: The name of the host to reboot.
    
    Returns:
      message: A success message.
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
