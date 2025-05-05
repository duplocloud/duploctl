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
  
  @Command("ls")
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
  def list_users(self, 
               name: args.NAME) -> dict:
    """List users assigned to a tenant
    
    Retrieve a list of all users with access to a tenant

    Usage: Basic CLI Use
      ```bash
      duploctl tenant list_users
      ```
    
    Returns:
      users (list): A list of users with access to the tenants, their readonly status, and if they're an admin user
    """
    tenant = self.find(name)
    tenant_id = tenant["TenantId"]
    response = self.duplo.get("admin/GetAllTenantAuthInfo")
    tenant_users = []
    for tenant in response.json():
        if tenant["TenantId"] == tenant_id:
            for user in tenant['UserAccess']:
                tenant_users.append({
                    "Username": user['Username'],
                    "IsReadOnly": f"{user['Policy']['IsReadOnly']}",
                    "IsAdmin": "False"
                })

    # Admins have access to all tenants. Check for them and add them
    users = self.duplo.get("admin/GetAllUserRoles")
    for user in users.json():
        if "Administrator" in user['Roles']:
            # If the user is already in the list for the tenant, mark them as admins. This shouldn't be possible.
            existing_user = next((u for u in tenant_users if u['Username'] == user['Username']), None)
            if existing_user:
              for user in tenant_users:
                  if user == existing_user:
                      user["IsAdmin"] = True
                      break
            else:
                tenant_users.append({
                    "Username": user['Username'],
                    "IsReadOnly": "False",
                    "IsAdmin": "True"
                })
    
    return tenant_users

  @Command("get")
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
      ref = name.lower() if name else self.duplo.tenant
    try:
      return [t for t in self.list() if t[key] == ref][0]
    except IndexError:
      raise DuploError(f"Tenant '{ref}' not found", 404)
  
  @Command()
  def create(self, 
             body: args.BODY) -> dict:
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
    if self.duplo.wait:
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

  @Command()
  def start(self, 
            name: args.NAME = None, 
            exclude: args.EXCLUDE=None) -> dict:
    """Start Tenant All Resources

    Starts all resources of a tenant.

    Usage: Basic CLI Use
      ```bash
      duploctl tenant start
      ```

    Args:
      wait: Wait for the resources to start.
      exclude (optional): A list of resources to exclude from starting. Can include:
        - hosts/<host_name>: Exclude a specific host.
        - rds/<rds_name>: Exclude a specific RDS instance.
        - hosts/at/<allocation_tags>: Exclude hosts with specific allocation tags.

    Returns:
      message: A success message.
    """
    service_types = {"hosts": [], "rds": []}
    host_at = []
    if exclude:
      for item in exclude:
        category, value = item.split('/', 1)
        if 'at/' in value:
          _, at_name = value.split('at/', 1)
          host_at.append(at_name)
        elif category in {"hosts", "rds"}:
          tenant_name = self.find(name)['AccountName']
          if category == "hosts":
            prefix = f"duploservices-{tenant_name}"
            value = f"{prefix}-{value}" if not value.startswith(prefix) else value
          elif category == "rds":
            value = f"duplo{value}" if not value.startswith("duplo") else value
          service_types[category].append(value)
        else:
          print(f"Unknown service: {category}")

    host_at_exclude = self.get_hosts_to_exclude(host_at)
    service_types['hosts'] = list(set(service_types['hosts']) | set(host_at_exclude))

    for service_type in service_types.keys():
      service = self.duplo.load(service_type)
      for item in service.list():
        service_name = service.name_from_body(item)
        if service_name not in service_types[service_type]:
          service.start(service_name, self.duplo.wait)
    return {
      "message": "Successfully started all resources for tenant"
    }

  @Command()
  def stop(self, 
           name: args.NAME = None,
           exclude: args.EXCLUDE=None) -> dict:
    """Stop Tenant All Resources

    Stops all resources of a tenant.

    Usage: Basic CLI Use
      ```bash
      duploctl tenant stop
      ```

    Args:
      wait: Wait for the resources to stop.
      exclude (optional): A list of resources to exclude from stopping. Can include:
        - hosts/<host_name>: Exclude a specific host.
        - rds/<rds_name>: Exclude a specific RDS instance.
        - hosts/at/<allocation_tags>: Exclude hosts with specific allocation tags.

    Returns:
      message: A success message.
    """
    service_types = {"hosts": [], "rds": []}
    host_at = []
    if exclude:
      for item in exclude:
        category, value = item.split('/', 1)
        if 'at/' in value:
          _, at_name = value.split('at/', 1)
          host_at.append(at_name)
        elif category in {"hosts", "rds"}:
          tenant_name = self.find(name)['AccountName']
          if category == "hosts":
            prefix = f"duploservices-{tenant_name}"
            value = f"{prefix}-{value}" if not value.startswith(prefix) else value
          elif category == "rds":
            value = f"duplo{value}" if not value.startswith("duplo") else value
          service_types[category].append(value)
        else:
          print(f"Unknown service: {category}")

    host_at_exclude = self.get_hosts_to_exclude(host_at)
    service_types['hosts'] = list(set(service_types['hosts']) | set(host_at_exclude))

    for service_type in service_types.keys():
      service = self.duplo.load(service_type)
      for item in service.list():
        service_name = service.name_from_body(item)
        if service_name not in service_types[service_type]:
          service.stop(service_name, self.duplo.wait)
    return {
      "message": "Successfully stopped all resources for tenant"
    }

  def get_hosts_to_exclude(self, host_at):
    host_at_exclude = []
    hosts = self.duplo.load('hosts').list()
    for host in hosts:
      allocation_tags_value = ''
      minion_tags = host.get('MinionTags', [])
      for tag in minion_tags:
        if tag.get('Key') == 'AllocationTags':
          allocation_tags_value = tag.get('Value')

      if allocation_tags_value in host_at:
        host_at_exclude.append(host['FriendlyName'])
    return host_at_exclude

  @Command()
  def dns_config(self, 
                 name: args.NAME=None) -> dict:
    """Tenant DNS Config

    Retrieve DNS configuration for a tenant by name..

    Usage: Basic CLI Use
      ```sh
      duploctl tenant dns_config <name>
      ```

    Args:
      name: The name of the tenant.

    Returns:
      dns_config: A dictionary containing the DNS configuration of the tenant.
    """
    tenant = self.find(name)
    tenant_id = tenant["TenantId"]
    response = self.duplo.get(f"v3/subscriptions/{tenant_id}/aws/dnsConfig")
    return response.json()

  @Command()
  def add_user(self, 
               name: args.NAME) -> dict:
    """Add User to Tenant
    
    Usage: CLI Usage
      ```sh
      duploctl tenant add_user <user> --tenant <tenant_name>
      ```

    Args:
      name: The name of the user to add to the tenant.

    Returns:
      message: A message indicating the user was added to the tenant.
    """
    tenant_id = self.find(self.duplo.tenant)["TenantId"]
    res = self.duplo.post("admin/UpdateUserAccess", {
      "Policy": { "IsReadOnly": None },
      "Username": name,
      "TenantId": tenant_id
    })
    # check http response is 204
    if res.status_code != 204:
      raise DuploError(f"Failed to add user '{name}' to tenant '{self.duplo.tenant}'", res["status_code"])
    else:
      return f"User '{name}' added to tenant '{self.duplo.tenant}'"
    
  @Command()
  def remove_user(self, 
                 name: args.NAME) -> dict:
    """Remove a User from a Tenant
    
    Usage: CLI Usage
      ```sh
      duploctl tenant remove_user <user> --tenant <tenant_name>
      ```

    Args:
      name: The name of the user to remove from the tenant.

    Returns:
      message: A message indicating the user was removed from the tenant.
    """
    tenant_id = self.find(self.duplo.tenant)["TenantId"]
    res = self.duplo.post("admin/UpdateUserAccess", {
      "Policy": {},
      "Username": name,
      "TenantId": tenant_id,
      "State": "deleted"
    })

    # check http response is 204
    if res.status_code != 204:
      raise DuploError(f"Failed to remove user '{name}' from tenant '{self.duplo.tenant}'", res["status_code"])
    else:
      return f"User '{name}' removed from tenant '{self.duplo.tenant}'"
    