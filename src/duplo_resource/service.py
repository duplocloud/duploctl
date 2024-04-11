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
             wait: args.WAIT = False):
    """Update a service."""
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
    self.duplo.post(self.endpoint("ReplicationControllerChangeAll"), body)
    if wait:
      self.wait(old, body)
    return {
      "message": f"Successfully updated service '{body['Name']}'"
    }
  
  @Command()
  def create(self,
             body: args.BODY,
             wait: args.WAIT = False):
    """Create a service."""
    self.duplo.post(self.endpoint("ReplicationControllerUpdate"), body)
    if wait:
      self.wait(lambda: self.find(body["Name"]))
    return {
      "message": f"Successfully created service '{body['Name']}'"
    }

  @Command()
  def delete(self,
             name: args.NAME):
    """Delete a service."""
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
                      wait: args.WAIT = False):
    """Update number of replicas for a service.

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
                   wait: args.WAIT = False):
    """Update the image of a service.
    
    Args:
      name (str): The name of the service to update.
      image (str): The new image to use for the service.
    """
    service = self.find(name)
    current_image =  self.image_from_body(service)

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
                 wait: args.WAIT = False):
    """Update the environment variables of a service.

    Args:
      name (str): The name of the service to update.
      setvar/-V (list): A list of key value pairs to set as environment variables.
      strategy/strat (str): The merge strategy to use for env vars. Valid options are "merge" or "replace".  Default is merge.
      deletevar/-D (list): A list of keys to delete from the environment variables.
    """
    service = self.find(name)
    service["Replicaset"] = self.current_replicaset(name)
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
      self.wait(service, payload)
    return {"message": "Successfully updated environment variables for services"}
    
  
  @Command()
  def bulk_update_image(self, 
                  serviceimage: args.SERVICEIMAGE):
    """Update multiple services.
    
    Args:
      serviceimage/-S (string): takes n sets of two arguments, service name and image name. e.g -S service1 image1:tag -S service2 image2:tag
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
              name: args.NAME):
    """Restart a service.
    
    Args:
      name (str): The name of the service to restart.
    Returns: 
      A success message if the service was restarted successfully.
    Raises:
      DuploError: If the service could not be restarted.
    """
    self.duplo.post(self.endpoint(f"ReplicationControllerReboot/{name}"))
    return {"message": f"Successfully restarted service '{name}'"}
  
  @Command()
  def stop(self, 
           name: args.NAME):
    """Stop a service.
    
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
            name: args.NAME):
    """Start a service.
    
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
           name: args.NAME):
    """Get the pods for a service.
    
    Args:
      name (str): The name of the service to get pods for.
    Returns: 
      A list of pods for the service.
    Raises:
      DuploError: If the service could not be found.
    """
    pods = self.__pod_svc.list()
    return [
      pod for pod in pods
      if pod["Name"] == name and pod["ControlledBy"]["QualifiedType"] == "kubernetes:apps/v1/ReplicaSet"
    ]
  
  @Command()
  def logs(self,
           name: args.NAME,
           wait: args.WAIT = False):
    """Get the logs for a service."""
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
    return pods[0]["ControlledBy"]["NativeId"]
  
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
      faults = self.tenant_svc.faults()
      running = 0
      for p in pods:
        if p["ControlledBy"]["NativeId"] == old.get("Replicaset", None) and rollover:
          continue
        for f in faults:
          if f["Resource"]["Name"] == p["InstanceId"]:
            raise DuploFailedResource(f"Service {name} raised a fault.\n{f['Description']}")
        if ((p["CurrentStatus"] == p["DesiredStatus"]) and p["DesiredStatus"] == 1):
          running += 1
      if replicas != running:
        raise DuploError(f"Service {name} waiting for pods {running}/{replicas}", 400)
    super().wait(wait_check, 400, 11)
