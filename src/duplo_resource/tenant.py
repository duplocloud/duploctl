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
             tenant: args.BODY):
    """Create a new tenant."""
    self.duplo.post("admin/AddTenant", tenant)
    return {
      "message": f"Tenant '{tenant['AccountName']}' created"
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
