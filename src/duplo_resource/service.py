import time
from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV2
from duplocloud.errors import DuploError, DuploFailedResource
from duplocloud.commander import Command, Resource
from json import dumps, loads
import duplocloud.args as args

_STATUS_CODES = {
  "1": "Running",
  "3": "Pending",
  "4": "Waiting",
  "6": "Deleted",
  "7": "Failed",
  "11": "Succeeded"
}

@Resource("service")
class DuploService(DuploTenantResourceV2):
  """Duplocloud Service Resource
  
  This resource is used to manage services in Duplocloud. Using the `duploctl` command line tool, you can manage services with actions:
  
  Usage: Basic CLI Use  
    ```sh
    duploctl service <action>
    ```
  """
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self.paths = {
      "list": "GetReplicationControllers"
    }
    self.__pod_svc = self.duplo.load("pod")
    self.__old = None
    self.__updates = None
    self.__old_replicaset = None
    
  @Command()
  def update(self, 
             name: args.NAME,
             body: args.BODY = None,
             patches: args.PATCHES = None,
             wait: args.WAIT = False) -> dict:
    """Update a service.
    
    Update the state of a service.

    Usage: Basic CLI Use
      Update the replicas to 3 for a service.
      ```sh
      duploctl service update <service-name> --replace Replicas 3 
      ```
    
    Args:
      name: The name of the service to update.
      body: The body of the service to update.
      patches: A list of JSON patches as args to apply to the service.
        The options are `--add`, `--remove`, `--replace`, `--move`, and `--copy`.
        Then followed by `<path>` and `<value>` for `--add`, `--replace`, and `--test`.
      wait: Whether to wait for the service to update.
    
    """
    if (name is None and body is None):
      raise DuploError("No arguments provided to update service", 400)
    if name and body:
      body["Name"] = name
    if body is None:
      body = self.find(name)
    # before patching, save the original body if we need to wait
    old = None
    if wait:
      old = self.find(name) # should use the cache
      old["Replicaset"] = self.current_replicaset(name)
    if patches:
      body = self.duplo.jsonpatch(body, patches)
    if ((ttags := body["Template"].get("AllocationTags", None))
        and not body.get("AllocationTags", None)):
      body["AllocationTags"] = ttags
    body["OtherDockerConfig"] = body["Template"]["OtherDockerConfig"]
    self.duplo.post(self.endpoint("ReplicationControllerChangeAll"), body)
    if wait:
      self.wait(old, body)
    return {
      "message": f"Successfully updated service '{body['Name']}'"
    }
  
  @Command()
  def create(self,
             body: args.BODY,
             wait: args.WAIT = False) -> dict:
    """Create a service.
    
    Create a service in Duplocloud.
    
    Usage: Basic CLI Use
      ```sh
      duploctl service create --file service.yaml
      ```
      Contents of the `service.yaml` file
      ```yaml
      --8<-- "src/tests/data/service.yaml"
      ```

    Args:
      body: The service to create.
      wait: Wait for the service to be created.

    Returns:
      message: Success message.
    """
    self.duplo.post(self.endpoint("ReplicationControllerUpdate"), body)
    if wait:
      self.wait(lambda: self.find(body["Name"]))
    return {
      "message": f"Successfully created service '{body['Name']}'"
    }

  @Command()
  def delete(self,
             name: args.NAME) -> dict:
    """Delete a service.
    
    Delete a service in Duplocloud.

    Usage: Basic CLI Use
      ```sh
      duploctl service delete <service-name>
      ```

    Args:
      name: The name of the service to delete.

    Returns:
      message: Success message.
    """
    body = {
      "Name": name,
      "State": "delete"
    }
    self.duplo.post(self.endpoint("ReplicationControllerUpdate"), body)
    return {
      "message": f"Successfully deleted service '{name}'"
    }

  @Command()
  def update_replicas(self, 
                      name: args.NAME,
                      replica: args.REPLICAS,
                      wait: args.WAIT = False) -> dict:
    """Scale Service

    Update the number of replicas for a service.

    Usage: Basic CLI Use
      ```sh
      duploctl service update_replicas <service-name> <replicas>
      ```

    Args:
        name (str): The name of the service to update.
        replica (str): Number of replicas to set for service.
    """
    service = self.find(name)
    data = {
      "Name": name,
      "Replicas": replica,
      "AllocationTags": service["Template"].get("AllocationTags", "")
    }
    self.duplo.post(self.endpoint("ReplicationControllerChange"), data)
    if wait:
      self.wait(service, data)
    return {"message": f"Successfully updated replicas for service '{name}'"} 
  
  @Command()
  def update_image(self, 
                   name: args.NAME, 
                   image: args.IMAGE,
                   wait: args.WAIT = False) -> dict:
    """Update the image of a service.

    Update the image of a service.

    Usage: Basic CLI Use
      ```sh
      duploctl service update_image <service-name> <image-name>
      ```
    
    Args:
      name: The name of the service to update.
      image: The new image to use for the service.

    Returns:
      message: Success message
    """
    service = self.find(name)
    current_image =  self.image_from_body(service)
    data = None

    # needed before update starts, not needed if not waiting
    if wait:
      service["Replicaset"] = self.current_replicaset(name)

    if(current_image == image):
      self.duplo.post(self.endpoint(f"ReplicationControllerReboot/{name}"))
    else:
      data = {
        "Name": name,
        "Image": image,
        "AllocationTags": service["Template"].get("AllocationTags", "")
      }
      self.duplo.post(self.endpoint("ReplicationControllerChange"), data)
    if wait:
      self.wait(service, data)
    return {"message": f"Successfully updated image for service '{name}'"}
 
  @Command()
  def update_env(self, 
                 name: args.NAME,
                 setvar: args.SETVAR,
                 strategy: args.STRATEGY,
                 deletevar: args.DELETEVAR,
                 wait: args.WAIT = False) -> dict:
    """Update the environment variables of a service. If service has no environment variables set, use -strat replace to set new values.
    Usage: Basic CLI Use
      ```sh
      duploctl service update_env <service-name> --setvar env-key1 env-val1 --setvar env-key2 env-val2 --setvar env-key3 env-val3 -strat merge --host $DUPLO_HOST --tenant $DUPLO_TENANT --token $DUPLO_TOKEN
      ```
    Args:
      name (str): The name of the service to update.
      setvar/-V (list): A list of key value pairs to set as environment variables.
      strategy/strat (str): The merge strategy to use for env vars. Valid options are "merge" or "replace".  Default is merge.
      deletevar/-D (list): A list of keys to delete from the environment variables.
    """
    service = self.find(name)
    
    currentDockerconfig = loads(service["Template"]["OtherDockerConfig"])
    currentEnv = currentDockerconfig.get("Env", [])
    newEnv = []
    if setvar is not None:
      newEnv = [{"Name": i[0], "Value": i[1]} for i in setvar]
    if strategy == 'merge':
      d = {d['Name']: d for d in currentEnv + newEnv}
      mergedvars = list(d.values())
      currentDockerconfig['Env'] = mergedvars
    else:
      currentDockerconfig['Env'] = newEnv
    if deletevar is not None:
      for key in deletevar:
        currentDockerconfig['Env'] = [d for d in currentDockerconfig['Env'] if d['Name'] != key]
    payload = {
      "Name": name,
      "OtherDockerConfig": dumps(currentDockerconfig),
      "allocationTags": service["Template"].get("AllocationTags", "")
    }
    self.duplo.post(self.endpoint("ReplicationControllerChange"), payload)
    if wait:
      service["Replicaset"] = self.current_replicaset(name)
      self.wait(service, payload)
    return {"message": f"Successfully updated environment variables for service '{name}'"}
    
  @Command()
  def update_pod_label(self,
                 name: args.NAME,
                 setvar: args.SETVAR,
                 strategy: args.STRATEGY,
                 deletevar: args.DELETEVAR,
                 wait: args.WAIT = False):    
  
    """Update the pod labels of a service. If service has no pod labels set, use -strat replace to set new values.
    Usage: Basic CLI Use
      ```sh
      duploctl service update_pod_label <service-name> --setvar env-key1 env-val1 --setvar env-key2 env-val2 --setvar env-key3 env-val3 -strat merge --host $DUPLO_HOST --tenant $DUPLO_TENANT --token $DUPLO_TOKEN
      duploctl service update_pod_label <service-name> --setvar env-key1 env-val1 --setvar env-key2 env-val2 -strat replace --host $DUPLO_HOST --tenant $DUPLO_TENANT --token $DUPLO_TOKEN
      duploctl service update_pod_label <service-name> --deletevar env-key1 --host $DUPLO_HOST --tenant $DUPLO_TENANT --token $DUPLO_TOKEN
      
      ```
    Args:
      name: The name of the service to update.
      setvar/-V: A list of key value pairs to set as environment variables.
      strategy/strat: The merge strategy to use for env vars. Valid options are "merge" or "replace".  Default is merge.
      deletevar/-D: A list of keys to delete from the environment variables.
    """
    service = self.find(name)
    currentDockerconfig = loads(service["Template"]["OtherDockerConfig"])
    currentLabels = currentDockerconfig.get("PodLabels", [])
    newLabels = []
    if setvar is not None:
      newLabels = [{"Name": i[0], "Value": i[1]} for i in setvar]

    # merge new labels in existing labels (append)
    if strategy == 'merge':
      mergedLabels = currentLabels
      for vars in newLabels:
        mergedLabels[vars["Name"]] = vars["Value"]
      currentDockerconfig['PodLabels'] = mergedLabels

    else:
      # replace values of existing label
      for label, value in currentDockerconfig['PodLabels'].items():
        for vars in newLabels:
          if vars["Name"] not in currentDockerconfig['PodLabels']:
            label_name = vars["Name"]
            raise DuploError(f"Service {name} does not have Pod label '{label_name}', enter correct label.", 400)
          if vars["Name"] == label:
            currentDockerconfig['PodLabels'][label] = vars["Value"]

    if deletevar is not None:
      for key in deletevar:
        del currentDockerconfig['PodLabels'][key]
      
    payload = {
      "Name": name,
      "OtherDockerConfig": dumps(currentDockerconfig),
      "allocationTags": service["Template"].get("AllocationTags", "")
    }
    self.duplo.post(self.endpoint("ReplicationControllerChange"), payload)
    if wait:
      service["Replicaset"] = self.current_replicaset(name)
      self.wait(service, payload)
    return {"message": f"Successfully updated pod labels for service '{name}'"}
  
  @Command()
  def bulk_update_image(self, 
                        serviceimage: args.SERVICEIMAGE) -> dict:
    """Update multiple services.

    Bulk update the image of a services.

    Usage: Basic CLI Use
      ```sh
      duploctl service bulk_update_image -S <service-name-1> <image-name-1> -S <service-name-2> <image-name-2>
      ```
    
    Args:
      serviceimage: takes n sets of two arguments, service name and image name. e.g -S service1 image1:tag -S service2 image2:tag
    """
    payload = []
    for i in serviceimage:
      servicepair = dict([i])
      for name, image in servicepair.items():
        payloaditem = {}
        service = self.find(name)
        allocation_tags = service["Template"]["AllocationTags"]
        payloaditem["Name"] = name
        payloaditem["Image"] = image
        payloaditem["AllocationTags"] = allocation_tags
        payload.append(payloaditem)
    self.duplo.post(self.endpoint("ReplicationControllerBulkChangeAll"), payload)
    return {"message": "Successfully updated images for services"}

  @Command()
  def restart(self, 
              name: args.NAME) -> dict:
    """Restart a service.

    Restart a service.

    Usage: Basic CLI Use
      ```sh
      duploctl service restart <service-name>
      ```
    
    Args:
      name: The name of the service to restart.

    Returns: 
      A success message if the service was restarted successfully.

    Raises:
      DuploError: If the service could not be restarted.
    """
    self.duplo.post(self.endpoint(f"ReplicationControllerReboot/{name}"))
    return {"message": f"Successfully restarted service '{name}'"}
  
  @Command()
  def stop(self, 
           name: args.NAME) -> dict:
    """Stop a service.

    Stop a service.

    Usage: Basic CLI Use
      ```sh
      duploctl service stop <service-name>
      ```
    
    Args:
      name (str): The name of the service to stop.  

    Returns: 
      A success message if the service was stopped successfully.  
      
    Raises:
      DuploError: If the service could not be stopped.  
    """
    self.duplo.post(self.endpoint(f"ReplicationControllerStop/{name}"))
    return {"message": f"Successfully stopped service '{name}'"}
  
  @Command()
  def start(self, 
            name: args.NAME) -> dict:
    """Start a service.

    Start a service.

    Usage: Basic CLI Use
      ```sh
      duploctl service start <service-name>
      ```
    
    Args:
      name (str): The name of the service to start.

    Returns: 
      A success message if the service was started successfully.

    Raises:
      DuploError: If the service could not be started.
    """
    self.duplo.post(self.endpoint(f"ReplicationControllerstart/{name}"))
    return {"message": f"Successfully started service '{name}'"}

  @Command()
  def pods(self, 
           name: args.NAME) -> dict:
    """Get the pods for a service.
    
    Args:
      name: The name of the service to get pods for.
    Returns: 
      message: A list of pods for the service.
    Raises:
      DuploError: If the service could not be found.
    """
    def controlled_by_service(pod):
      cb = pod.get("ControlledBy", None)
      same_name = pod["Name"] == name
      if cb is None:
        return same_name
      else:
        return same_name and cb.get("QualifiedType", None) == "kubernetes:apps/v1/ReplicaSet" 
    pods = self.__pod_svc.list()
    return [ pod for pod in pods if controlled_by_service(pod) ]
  
  @Command()
  def logs(self,
           name: args.NAME,
           wait: args.WAIT = False) -> dict:
    """Service Logs
    
    Get the logs for a service.

    Usage: Basic CLI Use
      ```sh
      duploctl service logs <service-name>
      ```
    Args:
      name (str): The name of the service to get logs for.
      wait (bool): Whether to wait for logs to update.
    Returns:
      message: A success message.
    """
    def show_logs():
      pods = self.pods(name)
      for pod in pods:
        self.__pod_svc.logs(pod=pod)
    if wait:
      try:
        while True:
          show_logs()
          time.sleep(3)
      except KeyboardInterrupt:
        pass
    else:
      show_logs()

  def current_replicaset(self, name: str):
    """Get the current replicaset for a service.
    
    Args:
      name (str): The name of the service to get replicaset for.
    Returns: 
      The current replicaset for the service.
    Raises:
      DuploError: If the service could not be found.
    """
    pods = self.pods(name)
    cb = pods[0].get("ControlledBy", None)
    if cb is None:
      return None
    return cb.get("NativeId", None)
  
  def image_from_body(self, body):
    """Get the image from a service body.
    
    Args:
      body (dict): The body of the service.
    Returns: 
      The image for the service.
    """
    tpl = body.get("Template", {})
    containers = tpl.get("Containers", [])
    for c in containers:
      if c["Name"] == body["Name"]:
        return c["Image"]
    else:
      return body.get("DockerImage", body.get("Image", None))

  def wait(self, old, updates):
    """Wait for a service to update."""
    name = old["Name"]
    cloud = old["Template"]["Cloud"]
    new_img = self.image_from_body(updates)
    old_img = self.image_from_body(old)
    new_replicas = updates.get("Replicas", None)
    replicas_changed = (old["Replicas"] != new_replicas) if new_replicas else False
    image_changed = (old_img != new_img) if new_img else False
    new_conf = updates.get("OtherDockerConfig", None)
    conf_changed = (old["Template"].get("OtherDockerConfig", None) != new_conf) if new_conf else False
    rollover = False
    if image_changed or conf_changed:
      rollover = True
    def check_pod_faults(pod, faults):
      """Check if the pod has any faults.
      
      This is for aws and gke because the faults are at the pod level.
      """
      for f in faults:
        if f["Resource"]["Name"] == pod["InstanceId"]:
          raise DuploFailedResource(f"Pod {pod['InstanceId']} raised a fault.\n{f['Description']}")
    def check_service_faults(faults):
      """Check if the service has any faults.
      
      This is only for azure because the faults are at the service level only
      """
      for f in faults:
        if f["ResourceName"] == name:
          raise DuploFailedResource(f"Service {name} raised a fault.\n{f['Description']}")
    def wait_check():
      svc = self.find(name)
      replicas = svc["Replicas"]
      # make sure the change has been applied
      if (image_changed and self.image_from_body(svc) != new_img):
        raise DuploError(f"Service {name} waiting for image update", 400)
      if (replicas_changed and replicas != new_replicas):
        raise DuploError(f"Service {name} waiting for replicas update", 400)
      if (conf_changed and svc["Template"].get("OtherDockerConfig", None) != new_conf):
        raise DuploError(f"Service {name} waiting for pod to update", 400)
      pods = self.pods(name)
      faults = self.tenant_svc.faults(id=self.tenant_id)
      running = 0

      # check for azure faults on service
      if cloud == 2:
        check_service_faults(faults)
      for p in pods:

        # azure doesn't have controlled by, so we skip this check if it's not there
        cb = p.get("ControlledBy", None) 
        # skip if the pod is not controlled by the new replicaset
        if (cloud != 2 and cb is not None) and (cb["NativeId"] == old.get("Replicaset", None) and rollover):
          continue

        # ignore this pod if the image is the old image
        img = p["Containers"][0]["Image"].removeprefix("docker.io/library/")
        if image_changed and img == old_img:
          continue

        # check for aws and gke faults on pod
        if cloud != 2:
          check_pod_faults(p, faults)

        # update total running pod count if one is running 
        if ((p["CurrentStatus"] == p["DesiredStatus"]) and p["DesiredStatus"] == 1):
          self.duplo.logger.warn(f"Pod {p['InstanceId']} is running")
          running += 1

      # make sure all the replicas are up
      if replicas != running:
        raise DuploError(f"Service {name} waiting for pods {running}/{replicas}", 400)
      
    # send to the base class to do the waiting
    super().wait(wait_check, 400, 11)

  def name_from_body(self, body):
    return body["Name"]
