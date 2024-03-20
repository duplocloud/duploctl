from datetime import timedelta
import datetime
from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("tenant")
class DuploTenant(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self):
    """Retrieve a list of all tenants in the Duplo system."""
    response = self.duplo.get("adminproxy/GetTenantNames")
    return response.json()

  @Command()
  def find(self, 
           name: args.NAME):
    """Find a tenant by name."""
    try:
      return [t for t in self.list() if t["AccountName"] == name][0]
    except IndexError:
      raise DuploError(f"Tenant '{name}' not found", 404)
  
  @Command()
  def create(self, 
             body: args.BODY,
             wait: args.WAIT=False):
    """Create a new tenant."""
    self.duplo.post("admin/AddTenant", body)
    def wait_check():
      self.find(body["AccountName"])
    if wait:
      self.wait(wait_check)
    return {
      "message": f"Tenant '{body['AccountName']}' created"
    }
  
  @Command()
  def delete(self,
             name: args.NAME):
    """Delete a tenant."""
    tenant = self.find(name)
    tenant_id = tenant["TenantId"]
    self.duplo.post(f"admin/DeleteTenant/{tenant_id}", None)
    return {
      "message": f"Tenant '{name}' deleted"
    }
    
  @Command()
  def shutdown(self, 
               name: args.NAME, 
               schedule: args.SCHEDULE=None):
    """Expire a tenant."""
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
      return f"Tenant '{name}' will shutdown on {schedule}"
    else:
      raise DuploError(f"Failed to expire tenant '{name}'", res.status_code)

  @Command()
  def logging(self, 
              name: args.NAME, 
              enable: args.ENABLE=True):
    """Enable or disable tenant logging."""
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
      return f"Tenant '{name}' logging {enable}"
    else:
      raise DuploError(f"Failed to {'enable' if enable else 'disable'} tenant '{name}'", res.status_code)

  @Command()
  def billing(self,
           name: args.NAME):
    """Spend
    
    Get the spend for the tenant. 
    """
    tenant = self.find(name)
    tenant_id = tenant["TenantId"]
    response = self.duplo.get(f"v3/billing/subscriptions/{tenant_id}/aws/billing")
    return response.json()
  
  @Command()
  def config(self,
               name: args.NAME,
               setvar: args.SETVAR=[],
               deletevar: args.DELETEVAR=[]):
    """Add a setting to the tenant."""
    updates = []
    creates = []
    changes = []
    tenant = self.find(name)
    tenant_id = tenant["TenantId"]
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
      response = self.duplo.post(f"v3/admin/tenant/{tenant_id}/metadata", s)
      change = response.json()
      change["Operation"] = "create"
      changes.append(change)
    for s in updates:
      response = self.duplo.put(f"v3/admin/tenant/{tenant_id}/metadata/{s['Key']}", s)
      change = response.json()
      change["Operation"] = "update"
      changes.append(change)
    for k in deletevar:
      if k in curr_keys:
        self.duplo.delete(f"v3/admin/tenant/{tenant_id}/metadata/{k}")
        change = {"Key": k, "Operation": "delete"}
        changes.append(change)
    return {
      "message": f"Successfully updated settings for tenant '{name}'",
      "changes": changes
    }
    
