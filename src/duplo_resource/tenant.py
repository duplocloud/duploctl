from datetime import timedelta
import datetime
from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("tenant")
class DuploTenant(DuploResource):
  """Duplo Tenant Resource
  
  The tenant resource provides a set of commands to manage tenants in the Duplo system.

  Usage: Basic CLI Use  
    ```sh
    duploctl tenant <action>
    ```
  """
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self):
    """List Tenants
    
    Retrieve a list of all tenants in the Duplo system. 

    Usage: Basic CLI Use
      ```bash
      duploctl tenant list
      ```
    
    Returns:
      tenants (list): A list of tenants.
    """
    response = self.duplo.get("adminproxy/GetTenantNames")
    return response.json()

  @Command()
  def find(self, 
           name: args.NAME=None,
           id: str=None) -> dict:
    """Find a tenant.

    Find a tenant by name or id. Passing in a name directly takes highest precedence.
    If a name is not passed in, the id is second highest precedence. Lastly if the global
    tenant name is set, that will be used. 

    The global tenant id takes care of the commandline. For other code, sometimes the id 
    needs to be passed in directly. If this happens, that id takes most precedence.

    Usage: Basic CLI Use
      ```bash
      duploctl tenant find <name>
      ```

    Args:
      name: The name or id of the tenant to find.
      id: The id of the tenant to find. Optional and code only.
    
    Returns:
      tenant: The tenant.
    """
    key = None 
    ref = None 
    if id or (not name and self.duplo.tenantid):
      key = "TenantId"
      ref = id or self.duplo.tenantid
    else:
      key = "AccountName"
      ref = name or self.duplo.tenant
    try:
      return [t for t in self.list() if t[key] == ref][0]
    except IndexError:
      raise DuploError(f"Tenant '{ref}' not found", 404)
  
  @Command()
  def create(self, 
             body: args.BODY,
             wait: args.WAIT=False) -> dict:
    """Create Tenant.
    
    Create a new tenant with a new body for a tenant. 

    Usage: Basic CLI Use
      ```bash
      duploctl tenant create --file tenant.yaml
      ```

    Example: Tenant Body
      Contents of the `tenant.yaml` file
      ```yaml
      --8<-- "src/tests/data/tenant.yaml"
      ```

    Example: Create One Liner
      Here is how to create a tenant in one line.  
      ```bash
      echo \"\"\"
      --8<-- "src/tests/data/tenant.yaml"
      \"\"\" | duploctl tenant create -f -
      ```
    
    Args:
      body: The body of the tenant to create.
      wait: Wait for the tenant to be created.

    Returns:
      message: The message that the tenant was created
    """
    name = body["AccountName"]
    self.duplo.post("admin/AddTenant", body)
    def wait_check():
      self.find(name)
    if wait:
      self.wait(wait_check)
    return {
      "message": f"Tenant '{name}' created"
    }
  
  @Command()
  def delete(self,
             name: args.NAME=None) -> dict:
    """Delete Tenant

    Delete a tenant by name.

    Usage: Basic CLI Use
      ```sh
      duploctl tenant delete <name>
      ```
    
    Args:
      name: The name of the tenant to delete.
    
    Returns:
      message: The message that the tenant was deleted.
    """
    tenant = self.find(name)
    tenant_id = tenant["TenantId"]
    self.duplo.post(f"admin/DeleteTenant/{tenant_id}", None)
    return {
      "message": f"Tenant '{name}' deleted"
    }
    
  @Command()
  def shutdown(self, 
               name: args.NAME=None, 
               schedule: args.SCHEDULE=None) -> dict:
    """Shutdown Tenant
    
    Shutdown a tenant by name and with a schedule.

    Usage: Basic CLI Use
      ```bash
      // Below command shutdown the tenant after 5 minutes (default)
      duploctl tenant shutdown <tenant-name>
      // Below command shutdown the tenant after given time 'minutes'(m), 'hours'(h) and 'day'(d) and it also support overriding the shutdown time.
      duploctl tenant shutdown <tenant-name> <time) // Example: 5m, 2h, 1d
      ```

    Args:
      name: The name of the tenant to shutdown.
      schedule: The schedule to shutdown the tenant.
    
    Returns:
      message: The message that the tenant was shutdown
    """
    tenant = self.find(name)
    tenant_id = tenant["TenantId"]
    # if the schedule not specified then set the date 5 minute from now
    if schedule is None:
      now = datetime.datetime.now() + datetime.timedelta(minutes=5)
      schedule = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    else:
      interval, unit = int(schedule[:-1]), schedule[-1]
      # Calculate the timedelta based on the specified time interval
      if unit == 'm':
        delta = timedelta(minutes=interval)
      elif unit == 'h':
        delta = timedelta(hours=interval)
      elif unit == 'd':
        delta = timedelta(days=interval)
      else:
          raise ValueError("Invalid time unit specified. Please use 'm' for minutes, 'h' for hours, or 'd' for days.")

      current_time = datetime.datetime.utcnow()
      # Calculate the future time after adding the timedelta
      future_time = current_time + delta
      # Format the future time in the desired string format
      schedule = future_time.strftime("%a, %d %b %Y %H:%M:%S GMT")

    res = self.duplo.post("adminproxy/UpdateTenantCleanupTimers", {
      "TenantId": tenant_id,
      "PauseTime": schedule
    })

    if res.status_code == 200:
      return {
        "message": f"Tenant '{name}' will shutdown on {schedule}"
      }
    else:
      raise DuploError(f"Failed to expire tenant '{name}'", res.status_code)

  @Command()
  def logging(self, 
              name: args.NAME=None, 
              enable: args.ENABLE=True) -> dict:
    """Toggle Loggine
    
    Enable or disable logging for a tenant.

    Usage: Basic CLI Use
      ```bash
      duploctl tenant logging <tenant-name> (default: true) // false not supported
      ```
    
    Args:
      name: The name of the tenant to toggle logging.
      enable: Enable or disable logging.
    
    Returns:
      message: The message that the tenant logging was toggled
    """
    tenant = self.find(name)
    tenant_id = tenant["TenantId"]
    # add or update the tenant in the list of enabled tenants
    response = self.duplo.get("admin/GetLoggingEnabledTenants")
    log_tenants = response.json()
    for t in log_tenants:
      if t["TenantId"] == tenant_id:
        t["Enabled"] = enable
        break
    else:
      log_tenants.append({"TenantId": tenant_id, "Enabled": enable})
    print(log_tenants)
    # update the entire list
    res = self.duplo.post("admin/UpdateLoggingEnabledTenants", log_tenants)
    if res.status_code == 200:
      return {
        "message": f"Tenant '{name}' logging {enable}"
      }
    else:
      raise DuploError(f"Failed to {'enable' if enable else 'disable'} tenant '{name}'", res.status_code)

  @Command()
  def billing(self,
              name: args.NAME=None) -> dict:
    """Tenant Billing Information
    
    Get the spend for the tenant.

    Usage: Basic CLI Use
      ```bash
      duploctl tenant billing <tenant-name>
      ```

    Args:
      name: The name of the tenant to get billing information for.

    Returns:
      billing: The billing information for the tenant.
    """
    tenant = self.find(name)
    tenant_id = tenant["TenantId"]
    response = self.duplo.get(f"v3/billing/subscriptions/{tenant_id}/aws/billing")
    return response.json()
  
  @Command()
  def config(self,
             name: args.NAME=None,
             setvar: args.SETVAR=[],
             deletevar: args.DELETEVAR=[]) -> dict:
    """Manage Tenant Settings
    
    Send a series of new settings and even some to delete.

    Usage: Basic CLI Use
      ```bash
      duploctl tenant config <tenant-name> --setvar <key> <value> --deletevar key3
      ```

    Args:
      name: The name of the tenant to manage.
      setvar: A series of key value pairs to set.
      deletevar: The keys to delete.
    
    Returns:
      message: The message that the tenant settings were updated.
    """
    updates = []
    creates = []
    changes = []
    tenant = self.find(name)
    tenant_id = tenant["TenantId"]
    endpoint = f"v3/admin/tenant/{tenant_id}/metadata"
    curr_settings = tenant.get("Metadata", [])
    curr_keys = [s["Key"] for s in curr_settings]
    # flatten k/v pair while dedupe and remove deleted keys
    new_settings = {s[0]: s[1] for s in setvar if s[0] not in deletevar}
    # only update if the value is different and create if the key is not present
    for k, v in new_settings.items():
      s = {"Key": k, "Value": v}
      for c in curr_settings:
        if c["Key"] == k:
          if c["Value"] != v:
            updates.append(s)
          break
      else:
        creates.append(s)
    # create, update, and delete the settings
    for s in creates:
      response = self.duplo.post(endpoint, s)
      change = response.json()
      change["Operation"] = "create"
      changes.append(change)
    for s in updates:
      response = self.duplo.put(f"{endpoint}/{s['Key']}", s)
      change = response.json()
      change["Operation"] = "update"
      changes.append(change)
    for k in deletevar:
      if k in curr_keys:
        self.duplo.delete(f"{endpoint}/{k}")
        change = {"Key": k, "Operation": "delete"}
        changes.append(change)
    return {
      "message": f"Successfully updated settings for tenant '{name}'",
      "changes": changes
    }
    
  @Command()
  def host_images(self,
                  name: args.NAME = None) -> list:
    """Available Duplo Host Images
    
    Get the list of host images for the tenant. These AMI's are region scoped. 

    Usage: Basic CLI Use
      ```bash
      duploctl tenant host_images <tenant-name>
      ```

    Args:
      name: The name of the tenant to get host images for.

    Returns:
      host_images: A list of host images.
    """
    tenant = self.find(name)
    tenant_id = tenant["TenantId"]
    response = self.duplo.get(f"v3/subscriptions/{tenant_id}/nativeHostImages")
    return response.json()

  @Command()
  def faults(self,
             name: args.NAME = None,
             id: str = None) -> list:
    """Tenant Faults
    
    Retrieves the list of faults for a tenant.

    Usage: Basic CLI Use
      ```bash
      duploctl tenant faults <tenant-name>
      ```

    Args:
      name: The name of the tenant to get faults for.
      id: The id of the tenant to get faults for. Optional and code only.
    
    Returns:
      faults: A list of faults.
    """
    tenant = self.find(name, id)
    tenant_id = tenant["TenantId"]
    response = self.duplo.get(f"subscriptions/{tenant_id}/GetFaultsByTenant")
    return response.json()
  
  @Command()
  def region(self,
             name: args.NAME = None) -> dict:
    """Tenant Region
    
    Get the region the tenants infrastructure is placed in.

    Usage: Basic CLI Use
      ```bash
      duploctl tenant region <tenant-name>
      ```
    
    Args:
      name: The name of the tenant to get the region for.

    Returns:
      region: The region the tenant is in.
    """
    tenant = self.find(name)
    tenant_id = tenant["TenantId"]
    response = self.duplo.get(f"subscriptions/{tenant_id}/GetAwsRegionId")
    return {
      "region": response.json()
    }
