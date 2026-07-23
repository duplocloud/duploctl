import json

from duplocloud.controller import DuploCtl
from duplocloud.resource import DuploResourceV2
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("asg", scope="tenant")
class DuploAsg(DuploResourceV2):
  """Manage Duplo ASGs

  Duplo ASGs (Auto Scaling Groups) manage the number of hosts within a tenant, enabling automatic scaling of instances based on demand.

  See more details at: https://docs.duplocloud.com/docs/overview/use-cases/hosts-vms/auto-scaling/auto-scaling-groups
  """
  
  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)
  
  @Command()
  def list(self) -> list:
    """List all ASGs.

    Retrieve the list of all Auto Scaling Groups in the tenant.

    Usage: CLI Usage
      ```sh
      duploctl asg list
      ```

    Returns:
      list: A list of all ASGs with their configurations.
    """
    tenant_id = self.tenant["TenantId"]
    response = self.client.get(f"subscriptions/{tenant_id}/GetTenantAsgProfiles")
    return response.json()

  @Command()
  def find(self, 
           name: args.NAME):
    """Find an ASG by name.

    Retrieve details of a specific Auto Scaling Group by its name.

    Usage: CLI Usage
      ```sh
      duploctl asg find <name>
      ```

    Args:
      name: The name of the ASG to find.

    Returns:
      dict: The ASG configuration including capacity, instance types, and other settings.

    Raises:
      DuploError: If the ASG with the specified name could not be found.
    """
    try:
      return [s for s in self.list() if s["FriendlyName"] == name][0]
    except IndexError:
      raise DuploNotFound(name, "ASG Profile")
    
  @Command(model="AsgProfile")
  def create(self,
             body: args.BODY) -> dict:
    """Create an ASG.

    Creates a new Auto Scaling Group with the specified configuration. The ASG will manage
    EC2 instances based on the defined capacity settings and scaling policies.
    
    Usage: CLI Usage
      ```sh
      duploctl asg create -f 'asg.yaml'
      ```
      Contents of the `asg.yaml` file
      ```yaml
      --8<-- "src/tests/data/asg.yaml"
      ```

    Example: Create an ASG using a one-liner.
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/asg.yaml"
      \"\"\" | duploctl asg create -f -
      ```

    Args:
      body: The complete ASG configuration including instance type, capacity settings,
            and other parameters.
      wait: Whether to wait for the ASG to be fully created and ready.

    Returns:
      message: Success message and the created ASG configuration.

    Raises:
      DuploError: If the ASG could not be created due to invalid configuration or API errors.
    """
    tenant_id = self.tenant["TenantId"]
    name = self.name_from_body(body)
    if body.get("ImageId", None) is None:
      body["ImageId"] = self.discover_image(body.get("AgentPlatform", 0))
    res = self.client.post(f"subscriptions/{tenant_id}/UpdateTenantAsgProfile", body)
    def wait_check():
      return self.find(name)
    if self.duplo.wait:
      self.wait(wait_check)
    return {
      "message": f"Successfully created asg '{body['FriendlyName']}'",
      "data": res.json()
    }
  
  @Command(model="AsgProfile")
  def update(self,
             body: args.BODY) -> dict:
    """Update an ASG.

    Update an existing Auto Scaling Group's configuration. This can include changes to
    capacity settings, instance types, scaling policies, and other parameters.

    Usage: CLI Usage
      ```sh
      duploctl asg update -f <file>
      ```
    
    Args:
      body: The updated ASG configuration. Must include the FriendlyName of the existing ASG.

    Returns:
      message: Success message and the updated ASG configuration.

    Raises:
      DuploError: If the ASG could not be updated due to invalid configuration or API errors.
    """
    tenant_id = self.tenant["TenantId"]
    res = self.client.post(f"subscriptions/{tenant_id}/UpdateTenantAsgProfile", body)
    return {
      "message": f"Successfully updated asg '{body['FriendlyName']}'",
      "data": res.json()
    }

  @Command()
  def delete(self,
             name: args.NAME) -> dict:
    """Delete an ASG.

    Delete an Auto Scaling Group by its name. This will terminate all instances
    managed by the ASG and remove the ASG configuration.

    Usage: CLI Usage
      ```sh
      duploctl asg delete <name>
      ```

    Args:
      name: The name of the ASG to delete.

    Returns:
      message: Success message confirming the ASG deletion.

    Raises:
      DuploError: If the ASG could not be deleted or does not exist.
    """
    tenant_id = self.tenant["TenantId"]
    body = { 
      "FriendlyName": name,
      "State": "delete"
    }
    res = self.client.post(f"subscriptions/{tenant_id}/UpdateTenantAsgProfile", body)
    return {
      "message": f"Successfully deleted asg '{name}'",
      "data": res.json()
    }

  @Command()
  def scale(self,
            name: args.NAME,
            min: args.MIN=None,
            max: args.MAX=None) -> dict:
    """Scale an ASG.

    Modify the capacity limits of an Auto Scaling Group. You can set new minimum and/or
    maximum instance counts. The ASG will automatically adjust the number of running
    instances to stay within these new bounds.

    Usage: CLI Usage
      ```sh
      duploctl asg scale <name> [-m <min>] [-M <max>]
      ```

    Args:
      name: The name of the ASG to scale (positional).
      min: The new minimum number of instances the ASG should maintain. Use -m flag to set.
      max: The new maximum number of instances the ASG can scale to. Use -M flag to set.

    Returns:
      message: Success message with the new scaling configuration.

    Raises:
      DuploError: If neither min nor max is provided, or if the scaling operation fails.
    """
    if min is None and max is None:
      raise DuploError("Must provide either min or max")
    asg = self.find(name)
    data = {
      "FriendlyName": name,
      "DesiredCapacity": asg.get("MinSize", None),
      "MinSize": asg.get("MinSize", None),# this really is a string unlike the other two? 
      "MaxSize": asg.get("MaxSize", None),
    }
    if min is not None:
      data["MinSize"] = str(min)
    if max is not None:
      data["MaxSize"] = max
    return self.update(data)
  
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

  @Command()
  def update_allocation_tags(self,
                            name: args.NAME,
                            allocationtags: args.ALLOCATION_TAGS) -> dict:
    """Update the allocation tag for an Auto Scaling Group.

    Updates the allocation tag for an existing Auto Scaling Group. The allocation tag
    is used to specify custom allocation rules for the ASG instances.

    Usage: CLI Usage
      ```sh
      duploctl asg update_allocation_tags <name> <allocationtags>
      ```

    Example: Update an ASG with new allocation tag
      ```sh
      duploctl asg update_allocation_tags duploservices-test-asg duploctl
      ```

    Args:
      name: The name of an existing ASG
      allocationtags: The new allocation tag value to set

    Returns:
      message: Success message and the updated ASG allocation tag.
    """
    asg = self.find(name)
    tenant_id = self.tenant["TenantId"]
    payload = {
        "ComponentId": asg["FriendlyName"],
        "ComponentType": 3,
        "Key": "AllocationTags",
        "Value": allocationtags,
        "State": "create"
    }
    self.client.post(f"subscriptions/{tenant_id}/UpdateCustomData", payload)
    return {"message": f"Successfully updated allocation tag for asg '{name}'"}

  # Key under which tenant stop/start snapshots an ASG's prior sizing so
  # start can restore it. Stored in the ASG's custom data (no ':' so it is
  # a valid AWS tag key). Not "AllocationTags", so it never affects
  # service placement.
  _SLEEP_KEY = "DuploctlSleepState"

  def _set_custom_data(self, asg_name, key, value, delete=False):
    """Set or clear one ASG custom-data key via UpdateCustomData.

    Writes land in the profile's ``CustomDataTags`` and are read back on
    the next ``list``/``find`` (the same channel as allocation tags).

    Args:
      asg_name: The prefixed FriendlyName of the ASG.
      key: The custom-data key.
      value: The value to store (ignored when deleting).
      delete: When True, remove the key instead of setting it.
    """
    tenant_id = self.tenant["TenantId"]
    payload = {
      "ComponentId": asg_name,
      "ComponentType": 3,  # ASG (see CustomComponentType enum)
      "Key": key,
      "Value": "" if delete else value,
      "State": "delete" if delete else "create",
    }
    self.client.post(f"subscriptions/{tenant_id}/UpdateCustomData", payload)

  def _get_custom_data(self, asg, key):
    """Read one custom-data value off an ASG profile body.

    Args:
      asg: An ASG profile body as returned by ``list``/``find``.
      key: The custom-data key to look up.

    Returns:
      The stored value, or None if the key is not present.
    """
    for kv in (asg.get("CustomDataTags") or []):
      if kv.get("Key") == key:
        return kv.get("Value")
    return None

  # Computed fields the backend returns but does not accept back on
  # update (Terraform's expandAsgProfile omits them too).
  _READONLY_ASG_FIELDS = ("Status", "AutoScalingGroupARN", "Created")

  def _apply_capacity(self, asg, min_size, max_size, desired,
                      can_scale_from_zero=None):
    """Update an ASG's capacity by re-sending its full profile.

    ``UpdateTenantAsgProfile`` validates and applies the *entire*
    submitted profile — omitted fields fall back to defaults. A sparse
    body therefore silently no-ops the capacity change and mis-validates
    flags such as ``CanScaleFromZero`` (which the backend rejects when
    set to ``true`` unless ``IsClusterAutoscaled`` is present and true;
    ``false`` is always accepted). So start from the current profile and
    override only the capacity fields, as the Terraform provider does.

    Args:
      asg: The full ASG profile body from ``list``/``find``.
      min_size: New minimum size.
      max_size: New maximum size.
      desired: New desired capacity.
      can_scale_from_zero: When set, overrides the CanScaleFromZero flag.
    """
    body = {k: v for k, v in asg.items()
            if k not in self._READONLY_ASG_FIELDS}
    body["MinSize"] = min_size
    body["MaxSize"] = max_size
    body["DesiredCapacity"] = desired
    if can_scale_from_zero is not None:
      body["CanScaleFromZero"] = can_scale_from_zero
    self.update(body)

  def stop_resources(self, exclude=()):
    """Scale every ASG to zero, snapshotting prior sizing first.

    Best-effort: each ASG's current MinSize/MaxSize/DesiredCapacity and
    CanScaleFromZero are stored as a JSON blob in the ASG's custom data
    before it is scaled to zero, so ``start_resources`` can restore them.
    An ASG that already carries a snapshot is assumed to be asleep and is
    left untouched, so a repeated stop never overwrites the snapshot with
    zeros. Genuine failures are collected and returned rather than
    aborting the sweep.

    info:
      This is not a cli command. It's primarily used internally but could be useful in a custom script.

    Args:
      exclude: ASG FriendlyNames to leave running.

    Returns:
      A list of (name, DuploError) for ASGs that failed to stop.
    """
    errors = []
    for asg in self.list():
      name = asg["FriendlyName"]
      if name in exclude:
        continue
      already_zero = (str(asg.get("MinSize")) == "0"
                      and str(asg.get("DesiredCapacity")) == "0")
      if self._get_custom_data(asg, self._SLEEP_KEY) is not None \
          and already_zero:
        # Genuinely asleep already — don't re-snapshot zeros over the
        # real sizing. A snapshot on a group that is NOT at zero is stale
        # (a prior stop failed after writing it), so fall through and
        # re-snapshot the real sizing before retrying the scale-down.
        continue
      try:
        snap = {
          "MinSize": asg.get("MinSize"),
          "MaxSize": asg.get("MaxSize"),
          "DesiredCapacity": asg.get("DesiredCapacity"),
          "CanScaleFromZero": asg.get("CanScaleFromZero", False),
        }
        self._set_custom_data(name, self._SLEEP_KEY, json.dumps(snap))
        try:
          # Cluster-autoscaled groups need CanScaleFromZero to sit at zero
          # nodes; the backend rejects setting it to true unless
          # IsClusterAutoscaled is true, so only enable it on autoscaled
          # groups (setting/leaving it false is always accepted).
          csfz = True if asg.get("IsClusterAutoscaled") else None
          self._apply_capacity(asg, 0, 0, 0, can_scale_from_zero=csfz)
        except DuploError:
          # Roll back the snapshot so a retry re-snapshots real sizing
          # instead of skipping this group as already asleep.
          self._set_custom_data(name, self._SLEEP_KEY, "", delete=True)
          raise
      except DuploError as e:
        self.duplo.logger.warning(f"Failed to stop asg '{name}': {e}")
        errors.append((name, e))
    return errors

  def start_resources(self, exclude=()):
    """Restore every asleep ASG from its snapshot, then clear it.

    Mirror of ``stop_resources``. ASGs without a snapshot are skipped
    (nothing to restore). Genuine failures are collected and returned.

    info:
      This is not a cli command. It's primarily used internally but could be useful in a custom script.

    Args:
      exclude: ASG FriendlyNames to leave stopped.

    Returns:
      A list of (name, DuploError) for ASGs that failed to start.
    """
    errors = []
    for asg in self.list():
      name = asg["FriendlyName"]
      if name in exclude:
        continue
      raw = self._get_custom_data(asg, self._SLEEP_KEY)
      if raw is None:
        continue
      try:
        snap = json.loads(raw)
        # Restore the *original* CanScaleFromZero from the snapshot: stop
        # may have flipped it to true on an autoscaled group, so start
        # must set it back. The snapshot value is false for non-autoscaled
        # groups, which the backend always accepts.
        self._apply_capacity(
          asg,
          snap["MinSize"],
          snap["MaxSize"],
          snap["DesiredCapacity"],
          can_scale_from_zero=snap.get("CanScaleFromZero", False),
        )
        self._set_custom_data(name, self._SLEEP_KEY, "", delete=True)
      except (DuploError, ValueError, KeyError) as e:
        self.duplo.logger.warning(f"Failed to start asg '{name}': {e}")
        errors.append((name, e))
    return errors
