from duplocloud.client import DuploClient
from duplocloud.errors import DuploStillWaiting
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("rds")
class DuploRDS(DuploTenantResourceV3):
  """Resource for managing RDS instances."""
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "aws/rds/instance")
    self.wait_timeout = 1200

  @Command()
  def create(self,
             body: args.BODY):
    """Create a DB instance.
    
    Args:
      body (dict): The body of the request.
    """
    name = self.name_from_body(body)
    s = None
    def wait_check():
      nonlocal s
      i = self.find(name)
      status = i.get("InstanceStatus", "submitted")
      if s != status:
        s = status
        self.duplo.logger.warn(f"DB instance {name} is {status}")
      if status != "available":
        raise DuploStillWaiting(f"DB instance '{name}' is waiting for status 'available'")
    super().create(body, self.duplo.wait, wait_check)

  @Command()
  def find_cluster(self,
                   name: args.NAME):
    """Find a DB instance by name.
    
    Args:
      name (str): The name of the DB instance to find.
    Returns: 
      The DB instance object.
    Raises:
      DuploError: If the DB instance could not be found.
    """
    response = self.duplo.get(self.endpoint(name, "groupDetails"))
    return response.json()
  
  @Command()
  def stop(self,
           name: args.NAME):
    """Stop a DB instance."""
    def wait_check():
      i = self.find(name)
      if i["InstanceStatus"] in ["stopping","available"]:
        raise DuploStillWaiting(f"DB instance {name} is still stopping")
    self.duplo.post(self.endpoint(name, "stop"))
    if self.duplo.wait:
      self.wait(wait_check, 1800, 10)
    return {
      "message": "DB instance stopped"
    }
  
  @Command()
  def start(self,
           name: args.NAME):
    """Start a DB instance."""
    def wait_check():
      i = self.find(name)
      if i["InstanceStatus"] in ["starting"]:
        raise DuploStillWaiting(f"DB instance {name} is still starting")
    self.duplo.post(self.endpoint(name, "start"))
    if self.duplo.wait:
      self.wait(wait_check, 1800, 10)
    return {
      "message": "DB instance started"
    }
  
  @Command()
  def reboot(self,
             name: args.NAME):
    """Reboot a DB instance."""
    rebooting = False
    def wait_check():
      nonlocal rebooting
      i = self.find(name)
      if i["InstanceStatus"] == "rebooting" and not rebooting:
        rebooting = True
      if i["InstanceStatus"] == "available" and rebooting:
        return True # finally rebooting is a success
      raise DuploStillWaiting(f"DB instance {name} is still rebooting")
    # Reboot the instance
    self.duplo.post(self.endpoint(name, "reboot"))
    if self.duplo.wait:
      self.wait(wait_check, 1800, 10)
    return {
      "message": "DB instance rebooted"
    }
  
  @Command()
  def set_instance_size(self,
                        name: args.NAME,
                        size: args.SIZE):
    """Set the size of a DB instance.
    
    Args:
      name (str): The name of the DB instance to update.
      size (str): The new size to use for the DB instance.
    """
    self.duplo.put(self.endpoint(name, "updatePayload"), {"SizeEx": size})
    return {
      "message": f"DB instance {name} resized to {size}"
    }
  
  @Command()
  def change_password(self,
                      name: args.NAME,
                      password: args.PASSWORD,
                      store: args.SAVE_SECRET):
    """Change the password of a DB instance.
    
    Args:
      name (str): The name of the DB instance to update.
      password (str): The new password to use for the DB instance.
    """
    body = {
      "Identifier": name,
      "MasterPassword": password,
      "StorePassword": store
    }
    self.duplo.post(self.endpoint(name, "changePassword"), body)
    return {
      "message": f"Password for DB instance {name} changed"
    }
  
  @Command()
  def set_monitor_interval(self,
                           name: args.NAME,
                           interval: args.INTERVAL,
                           immediate: args.IMMEDIATE=False):
    """Set the monitoring interval for a DB instance.
    
    Args:
      name (str): The name of the DB instance to update.
      interval (str): The new monitoring interval to use for the DB instance.
    """
    tenant_id = self.tenant["TenantId"]
    body = {
      "DBInstanceIdentifier": name,
      "ApplyImmediately": immediate, 
      "MonitoringInterval":interval
    }
    self.duplo.post(f"subscriptions/{tenant_id}/ModifyRDSDBInstance", body)
    return {
      "message": f"Monitoring interval for DB instance {name} set to {interval}"
    }
  
  @Command()
  def logging(self,
              name: args.NAME,
              enable: args.ENABLE):
    """Enable or disable logging for a DB instance."""
    self.duplo.put(self.endpoint(name, "updatePayload"), {"EnableLogging": enable})
    return {
      "message": f"DB instance {name} logging is {enable}"
    }
  
  @Command()
  def iam_auth(self,
               name: args.NAME,
               enable: args.ENABLE,
               immediate: args.IMMEDIATE=False):
    """Toggle IAM authentication for a DB instance."""
    body = {
      "DBInstanceIdentifier": name,
      "EnableIAMDatabaseAuthentication": enable,
      "ApplyImmediately": immediate
    }
    self.update(name=name, body=body)
    return {
      "message": f"IAM authentication for DB instance {name} is {enable}"
    }
  
  @Command()
  def final_snapshot(self,
                     name: args.NAME,
                     enable: args.ENABLE,
                     immediate: args.IMMEDIATE=False):
    """Toggle IAM authentication for a DB instance."""
    body = {
      "DBInstanceIdentifier": name,
      "SkipFinalSnapshot": not enable,
      "ApplyImmediately": immediate
    }
    self.update(name=name, body=body)
    return {
      "message": f"Final Snapshot for DB instance {name} is {enable}"
    }
  
  @Command()
  def snapshot(self,
               name: args.NAME):
    """Take a snapshot of a DB instance."""
    body = { "DBInstanceIdentifier": name }
    self.duplo.post(self.endpoint(name, "snapshot"), body)
    return {
      "message": f"Snapshot of DB instance {name} taken"
    }
  
  @Command()
  def restore(self,
              name: args.NAME,
              target: args.TARGET,
              time: args.TIME):
    """Restore a DB instance from a snapshot."""
    body = {
      "TargetName": target, 
      "RestoreTime": time
    }
    response = self.duplo.post(self.endpoint(name, "restorePointInTime"), body)
    return {
      "message": f"DB instance {name} restored to {target} at {time}",
      "data": response.json()
    }
  
  @Command()
  def retention_period(self,
                       name: args.NAME,
                       days: args.DAYS,
                       immediate: args.IMMEDIATE=False):
    """Set the retention period for a DB instance."""
    body = {
      "DBInstanceIdentifier": name,
      "BackupRetentionPeriod": days,
      "ApplyImmediately": immediate
    }
    self.update(name=name, body=body)
    return {
      "message": f"DB instance {name} retention period set to {days} days"
    }

  def name_from_body(self, body):
    other_name = body.get("DBInstanceIdentifier", None)
    name = body.get("Identifier", other_name)
    if not name.startswith("duplo"):
      name = "duplo" + name
    return name
