from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploStillWaiting
from duplocloud.resource import DuploResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args

# DBEngine enum values from the backend (RDSConfiguration.cs). Cluster
# engines (Aurora) support stop/start only at the cluster level, not on
# member instances. Serverless v1 auto-pauses and has no stop/start API.
# DocumentDB (13) is a cluster engine too, but its cluster stop/start is
# not yet validated end-to-end, so it is skipped for now.
_CLUSTER_ENGINES = {8, 9, 16}        # AuroraMySql, AuroraPostgreSql, Aurora
_SKIP_ENGINES = {11, 12, 13}         # Serverless v1 (MySql/PostgreSql), DocDB
_CLUSTER_ENGINE_NAMES = {"AuroraMySql", "AuroraPostgreSql", "Aurora"}
_SKIP_ENGINE_NAMES = {
  "AuroraServerlessMySql",
  "AuroraServerlessPostgreSql",
  "DocumentDB",
}

@Resource("rds", scope="tenant")
class DuploRDS(DuploResourceV3):
  """Resource for managing RDS instances."""
  
  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo, "aws/rds/instance")
    self.wait_timeout = 1200

  @Command(model="AmazonRDSRequest")
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
      try:
        i = self.find(name)
      except DuploError:
        raise DuploStillWaiting(f"DB instance '{name}' not yet visible")
      status = i.get("InstanceStatus", "submitted")
      if s != status:
        s = status
        self.duplo.logger.warning(f"DB instance {name} is {status}")
      if status != "available":
        raise DuploStillWaiting(f"DB instance '{name}' is waiting for status 'available'")
    return super().create(body, wait_check)

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
    response = self.client.get(self.endpoint(name, "groupDetails"))
    return response.json()
  
  @Command()
  def delete(self,
             name: args.NAME) -> dict:
    """Delete a DB instance by name.

    Usage: CLI Usage
      ```sh
      duploctl rds delete <name>
      ```

    Args:
      name: The name of the DB instance to delete.

    Returns:
      message: A success message.

    Raises:
      DuploError: If the DB instance could not be found or deleted.
    """
    self.client.delete(self.endpoint(name))
    return {
      "message": f"{name} deleted"
    }

  @Command()
  def stop(self,
           name: args.NAME):
    """Stop a DB instance, or its cluster for Aurora/cluster engines.

    Aurora and other cluster engines cannot be stopped at the member
    instance level; AWS only supports stop/start on the cluster. This
    command inspects the named resource's engine and routes to the
    correct existing endpoint. Aurora Serverless v1 auto-pauses and is
    skipped.

    Usage: CLI Usage
      ```sh
      duploctl rds stop <name>
      ```

    Args:
      name: The name of the DB instance to stop.

    Returns:
      message: A success message.
    """
    return self._route_action("stop", self.find(name))

  @Command()
  def start(self,
            name: args.NAME):
    """Start a DB instance, or its cluster for Aurora/cluster engines.

    Mirror of ``stop``: routes Aurora/cluster engines to the cluster
    start endpoint and regular RDS to the instance start endpoint.
    Aurora Serverless v1 resumes automatically and is skipped.

    Usage: CLI Usage
      ```sh
      duploctl rds start <name>
      ```

    Args:
      name: The name of the DB instance to start.

    Returns:
      message: A success message.
    """
    return self._route_action("start", self.find(name))

  def stop_resources(self, exclude=()):
    """Stop every RDS resource in the tenant with correct routing.

    Lists all RDS resources, classifies each by engine, and stops them:
    regular instances via the instance endpoint, Aurora/cluster engines
    via the cluster endpoint (deduped so a multi-node cluster is stopped
    once), and Aurora Serverless v1 / DocumentDB skipped. Errors meaning
    the resource is already stopped/stopping are treated as benign.

    Args:
      exclude: Instance identifiers to leave running.
    """
    return self._action_all("stop", exclude)

  def start_resources(self, exclude=()):
    """Start every RDS resource in the tenant with correct routing.

    Mirror of ``stop_resources``.

    Args:
      exclude: Instance identifiers to leave stopped.
    """
    return self._action_all("start", exclude)

  def _action_all(self, action, exclude=()):
    """Apply ``action`` ("stop"/"start") to all RDS resources, deduped."""
    seen_clusters = set()
    for body in self.list():
      name = self.name_from_body(body)
      if name in exclude:
        continue
      category = self._engine_category(body)
      if category == "skip":
        self.duplo.logger.warning(
          f"Skipping {name}: engine not eligible for stop/start"
        )
        continue
      if category == "cluster":
        cluster_id = body.get("ClusterIdentifier")
        if not cluster_id:
          self.duplo.logger.warning(
            f"Skipping {name}: cluster engine missing ClusterIdentifier"
          )
          continue
        if cluster_id in seen_clusters:
          continue  # one call per cluster, not per member
        seen_clusters.add(cluster_id)
      try:
        self._route_action(action, body)
      except DuploError as e:
        if self._is_benign_state_error(e):
          self.duplo.logger.warning(
            f"{name}: already in target state, skipping ({e})"
          )
        else:
          self.duplo.logger.warning(f"Skipping {name}: {e}")

  def _route_action(self, action, body):
    """Route a single RDS resource body to the correct stop/start call."""
    name = self.name_from_body(body)
    category = self._engine_category(body)
    if category == "skip":
      self.duplo.logger.warning(
        f"Skipping {name}: engine not eligible for stop/start"
      )
      return {"message": f"{name} skipped (engine not eligible)"}
    if category == "cluster":
      cluster_id = body.get("ClusterIdentifier")
      if not cluster_id:
        raise DuploError(
          f"{name} is a cluster engine but has no ClusterIdentifier", 400
        )
      return self._cluster_action(action, cluster_id)
    return self._instance_action(action, name)

  def _instance_action(self, action, name):
    """Stop/start a regular RDS instance via the instance endpoint."""
    target = "stopped" if action == "stop" else "available"
    def wait_check():
      i = self.find(name)
      if i["InstanceStatus"] != target:
        raise DuploStillWaiting(
          f"DB instance {name} is {i['InstanceStatus']}, "
          f"waiting for '{target}'"
        )
    self.client.post(self.endpoint(name, action))
    if self.duplo.wait:
      self.wait(wait_check, 1800, 10)
    verb = {"stop": "stopped", "start": "started"}[action]
    return {"message": f"DB instance {verb}"}

  def _cluster_action(self, action, cluster_id):
    """Stop/start an Aurora/cluster engine via the cluster endpoint."""
    path = (
      f"v3/subscriptions/{self.tenant_id}/aws/rds/cluster/"
      f"{cluster_id}/{action}"
    )
    self.client.post(path)
    verb = {"stop": "stopped", "start": "started"}[action]
    return {"message": f"DB cluster {cluster_id} {verb}"}

  def _engine_category(self, body):
    """Classify an RDS resource for stop/start routing.

    Returns "cluster", "instance", or "skip". The Engine field is the
    backend DBEngine enum, usually an integer; string engine names are
    accepted as a fallback.
    """
    engine = body.get("Engine")
    if isinstance(engine, str):
      if engine in _SKIP_ENGINE_NAMES:
        return "skip"
      if engine in _CLUSTER_ENGINE_NAMES:
        return "cluster"
      return "instance"
    if engine in _SKIP_ENGINES:
      return "skip"
    if engine in _CLUSTER_ENGINES:
      return "cluster"
    return "instance"

  def _is_benign_state_error(self, e):
    """True if the error means the resource is already in the target state."""
    msg = str(e).lower()
    return any(s in msg for s in (
      "invaliddbclusterstate",
      "invaliddbinstancestate",
      "not in available state",
      "not eligible for stopping",
      "not supported for aurora serverless",
    ))

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
    self.client.post(self.endpoint(name, "reboot"))
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
    self.client.put(self.endpoint(name, "updatePayload"), {"SizeEx": size})
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
    self.client.post(self.endpoint(name, "changePassword"), body)
    return {
      "message": f"Password for DB instance {name} changed"
    }
  
  @Command()
  def modify(self,
             name: args.NAME,
             body: args.BODY) -> dict:
    """Modify a DB instance via the ModifyRDSDBInstance endpoint.

    Sends an arbitrary request body to the AWS ModifyRDSDBInstance API
    for the named DB instance. Used internally by higher-level commands
    like iam_auth, final_snapshot, and retention_period.

    Usage: CLI Usage
      ```sh
      duploctl rds modify <name> -f payload.yaml
      ```

    Args:
      name: The name of the DB instance to modify.
      body: The ModifyRDSDBInstance request body.

    Returns:
      message: A success message.
    """
    body["DBInstanceIdentifier"] = name
    self.client.post(
      f"subscriptions/{self.tenant_id}/ModifyRDSDBInstance", body
    )
    return {
      "message": f"DB instance {name} modified"
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
    self.modify(name=name, body={
      "ApplyImmediately": immediate,
      "MonitoringInterval": interval
    })
    return {
      "message": f"Monitoring interval for DB instance {name} set to {interval}"
    }
  
  @Command()
  def logging(self,
              name: args.NAME,
              enable: args.ENABLE):
    """Enable or disable logging for a DB instance."""
    self.client.put(self.endpoint(name, "updatePayload"), {"EnableLogging": enable})
    return {
      "message": f"DB instance {name} logging is {enable}"
    }
  
  @Command()
  def iam_auth(self,
               name: args.NAME,
               enable: args.ENABLE,
               immediate: args.IMMEDIATE=False):
    """Toggle IAM authentication for a DB instance."""
    self.modify(name=name, body={
      "EnableIAMDatabaseAuthentication": enable,
      "ApplyImmediately": immediate
    })
    return {
      "message": f"IAM authentication for DB instance {name} is {enable}"
    }

  @Command()
  def final_snapshot(self,
                     name: args.NAME,
                     enable: args.ENABLE,
                     immediate: args.IMMEDIATE=False):
    """Toggle final snapshot for a DB instance."""
    self.modify(name=name, body={
      "SkipFinalSnapshot": not enable,
      "ApplyImmediately": immediate
    })
    return {
      "message": f"Final Snapshot for DB instance {name} is {enable}"
    }
  
  @Command()
  def snapshot(self,
               name: args.NAME):
    """Take a snapshot of a DB instance."""
    body = { "DBInstanceIdentifier": name }
    self.client.post(self.endpoint(name, "snapshot"), body)
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
    response = self.client.post(self.endpoint(name, "restorePointInTime"), body)
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
    self.modify(name=name, body={
      "BackupRetentionPeriod": days,
      "ApplyImmediately": immediate
    })
    return {
      "message": f"DB instance {name} retention period set to {days} days"
    }

  @Command()
  def engine_versions(self) -> dict:
    """List supported RDS engine versions and instance types."""
    path = f"v3/subscriptions/{self.tenant_id}/aws/rds/engineVersions"
    response = self.client.post(path, {})
    return response.json()

  def name_from_body(self, body):
    other_name = body.get("DBInstanceIdentifier", None)
    name = body.get("Identifier", other_name)
    if not name.startswith("duplo"):
      name = "duplo" + name
    return name
