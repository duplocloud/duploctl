import datetime
from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.errors import DuploError

class DuploTenant(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  def list(self):
    """Retrieve a list of all tenants in the Duplo system."""
    return self.duplo.get("adminproxy/GetTenantNames")

  def find(self, tenant_name):
    """Find a tenant by name."""
    try:
      return [t for t in self.list() if t["AccountName"] == tenant_name][0]
    except IndexError:
      raise DuploError(f"Tenant '{tenant_name}' not found", 404)
    
  def shutdown(self, tenant_name, schedule=None):
    """Expire a tenant."""
    tenant = self.find(tenant_name)
    tenant_id = tenant["TenantId"]

    # if the schedule not specified then set the date 5 minute from now
    if schedule is None:
      now = datetime.datetime.now() + datetime.timedelta(minutes=5)
      schedule = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    res = self.duplo.post("adminproxy/UpdateTenantCleanupTimers", {
      "TenantId": tenant_id,
      "PauseTime": schedule
    })

    if res.status_code == 200:
      return f"Tenant '{tenant_name}' will shutdown on {schedule}"
    else:
      raise DuploError(f"Failed to expire tenant '{tenant_name}'", res.status_code)

  def logging(self, tenant_name, enable=True):
    """Enable or disable tenant logging."""
    tenant = self.find(tenant_name)
    tenant_id = tenant["TenantId"]
    # add or update the tenant in the list of enabled tenants
    log_tenants = self.duplo.get("admin/GetLoggingEnabledTenants")
    for t in log_tenants:
      if t["TenantId"] == tenant_id:
        t["Enabled"] = enable
        break
    else:
      log_tenants.append({"TenantId": tenant_id, "Enabled": enable})
    # update the entire list
    res = self.duplo.post("admin/UpdateLoggingEnabledTenants", log_tenants)
    if res.status_code == 200:
      return f"Tenant '{tenant_name}' logging {enable}"
    else:
      raise DuploError(f"Failed to {'enable' if enable else 'disable'} tenant '{tenant_name}'", res.status_code)