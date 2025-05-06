import time
from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV2
from duplocloud.errors import DuploError, DuploFailedResource, DuploStillWaiting
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

  def _validate_args(self, name, all, targets):
    if sum(bool(x) for x in [name, all, targets]) > 1:
      raise DuploError("You can only specify one of: a service name, the '--all' flag, or the '--targets' flag.")
    if not any([name, all, targets]):
      raise DuploError("You must specify a service name, use the '--all' flag, or provide '--targets'.")

  def _process_service(self, action, service_name, results, wait):
    """Helper function to process a service action (start/stop) and handle errors."""
    try:
      endpoint_action = "ReplicationController" + action.capitalize()
      response = self.duplo.post(self.endpoint(f"{endpoint_action}/{service_name}"))

      if response.status_code == 200:
        results["success"].append(service_name)
        if wait:
          service = self.find(service_name)
          self.wait(service, service)
      else:
        results["errors"].append(
          {"service": service_name, "error": f"Unexpected response: {response}"}
        )
    except Exception as e:
      results["errors"].append({"service": service_name, "error": str(e)})

  def _perform_action(self, action, name=None, all=False, targets=None, wait=False):
    """Generic method to perform a start or stop action on services."""
    self._validate_args(name, all, targets)

    results = {"success": [], "errors": []}

    if all:
      services = self.list()
      for service in services:
        service_name = service["Name"]
        self._process_service(action, service_name, results, wait)
    elif targets:
      for service_name in targets:
        self._process_service(action, service_name, results, wait)
    else:
      self._process_service(action, name, results, wait)

    return {
      "message": f"Service {action} operation completed.",
      "details": results,
    }
    
  @Command()
  def update(self, 
             name: args.NAME,
             body: args.BODY = None,
             patches: args.PATCHES = None) -> dict:
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
    if self.duplo.wait:
      old = self.find(name) # should use the cache
      old["Replicaset"] = self.current_replicaset(name)
    if patches:
      body = self.duplo.jsonpatch(body, patches)
    if ((ttags := body["Template"].get("AllocationTags", None))
        and not body.get("AllocationTags", None)):
      body["AllocationTags"] = ttags
    body["OtherDockerConfig"] = body["Template"]["OtherDockerConfig"]
    body["AgentPlatform"] = body["Template"].get("AgentPlatform", 0)
    self.duplo.post(self.endpoint("ReplicationControllerChangeAll"), body)
    if self.duplo.wait:
      self.wait(old, body)
    return {
      "message": f"Successfully updated service '{body['Name']}'"
    }
  
  @Command()
  def create(self,
             body: args.BODY) -> dict:
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
    if self.duplo.wait:
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
                      replica: args.REPLICAS) -> dict:
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
    if self.duplo.wait:
      self.wait(service, data)
    return {"message": f"Successfully updated replicas for service '{name}'"} 
  
  @Command()
  def update_image(self, 
                   name: args.NAME, 
                   image: args.IMAGE = None,
                   container_image: args.CONTAINER_IMAGE = None,
                   init_container_image: args.INIT_CONTAINER_IMAGE = None) -> dict:
    """Update the image of a service.

    Usage: Basic CLI Use
      ```sh
      duploctl service update_image <service-name> <service-image>
      duploctl service update_image <service-name> --container-image <side-car-container> <container-image>
      duploctl service update_image <service-name> --init-container-image <init-container> <init-container-image>
      ```

    Args:
      name: The name of the service to update.
      image: The new image to use for the service.
      container_image: A list of key-value pairs to set as sidecar container image.
      init_container_image: A list of key-value pairs to set as init container image.
      wait: Whether to wait for the update to complete.

    Returns:
      message: Success message
    """
    if [image, container_image, init_container_image].count(None) != 2:
      raise DuploError("Provide a service image, container images, or init container images.")

    service = self.find(name)
    data = {}
    updated_containers = []
    not_found_containers = []

    if not image:
      other_docker_config = loads(service["Template"].get("OtherDockerConfig", "{}"))
      if container_image:
        images = container_image
        containers = other_docker_config.get("additionalContainers", [])
      elif init_container_image:
        images = init_container_image
        containers = other_docker_config.get("initContainers", [])

      for key, value in images:
        container_found = False
        for c in containers:
          if c["name"] == key:
            c["image"] = value
            updated_containers.append(key)
            container_found = True
            break
        if not container_found:
          not_found_containers.append(key)

      if not updated_containers:
        raise DuploError(f"No matching containers found in service '{name}'")

      data = {
        "Name": name,
        "OtherDockerConfig": dumps(other_docker_config),
        "AllocationTags": service["Template"].get("AllocationTags", "")
      }

    else:
      data = {
        "Name": name,
        "Image": image,
        "AllocationTags": service["Template"].get("AllocationTags", "")
      }

    self.duplo.post(self.endpoint("ReplicationControllerChange"), data)

    if self.duplo.wait:
      self.wait(service, data)

    response_message = "Successfully updated image for service."
    if updated_containers:
      response_message += f" Updated containers: {', '.join(updated_containers)}."
    if not_found_containers:
      response_message += f" Could not find containers: {', '.join(not_found_containers)}."

    return {"message": response_message}
 
  @Command()
  def update_env(self, 
                 name: args.NAME,
                 setvar: args.SETVAR,
                 strategy: args.STRATEGY,
                 deletevar: args.DELETEVAR) -> dict:
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
    # Returns an array of key and value mappings with provided keys
    def new_env_vars(setvar, key_name="Name", value_name="Value"):
      return [{key_name: i[0], value_name: i[1]} for i in setvar]
  
    def detect_case_format(env_list):
      # Check if the environment variables are using upper, lower, or mixed case for Name and Value
      if all('Name' in env and 'Value' in env for env in env_list):
          return "title"
      elif all('name' in env and 'value' in env for env in env_list):
          return "lower"
      # No consistent standard
      return "mixed"
    
    service = self.find(name)
    currentDockerconfig = loads(service["Template"]["OtherDockerConfig"])
    currentEnv = currentDockerconfig.get("Env", [])
    # Check if user is attempting to merge against a null Env. If so, set currentEnv to empty.
    if currentEnv is None and strategy == "merge":
      self.duplo.logger.warn("Specified \"merge\" strategy on a service with"
                             " no environment variables defined, should use "
                             " \"replace\". Proceeding anyway")
      currentEnv = []
    case_format = detect_case_format(currentEnv)
    if strategy == 'merge':
      try:
        if case_format == "title":
          newEnv = new_env_vars(setvar) if setvar is not None else []
          d = {env['Name']: env for env in currentEnv + newEnv}
        elif case_format == "lower":
          newEnv = new_env_vars(setvar, key_name="name", value_name="value") if setvar is not None else []
          d = {env['name']: env for env in currentEnv + newEnv}
        else:
          self.duplo.logger.warn("Possible attempt to merge env vars with"
                                 " inconsistent Name/Value key case."
                                 " Normalzing to capitalized"
                                 " \"Name\" and \"Value\"")
          norm_currentEnv = [{k.capitalize(): v for k, v in env.items()} for env in currentEnv]
          newEnv = new_env_vars(setvar,) if setvar is not None else []
          d = {env['Name']: env for env in norm_currentEnv + newEnv}
      except KeyError:
        raise DuploError("Could not merge new and existing environment variables")
      mergedvars = list(d.values())
      currentDockerconfig['Env'] = mergedvars
    else:
      newEnv = new_env_vars(setvar) if setvar is not None else []
      currentDockerconfig['Env'] = newEnv
    if deletevar is not None:
      for key in deletevar:
        try:
          currentDockerconfig['Env'] = [d for d in currentDockerconfig['Env'] if d['Name'] != key]
        except KeyError:
          currentDockerconfig['Env'] = [d for d in currentDockerconfig['Env'] if d['name'] != key] 
    payload = {
      "Name": name,
      "OtherDockerConfig": dumps(currentDockerconfig),
      "allocationTags": service["Template"].get("AllocationTags", "")
    }
    self.duplo.post(self.endpoint("ReplicationControllerChange"), payload)
    if self.duplo.wait:
      service["Replicaset"] = self.current_replicaset(name)
      self.wait(service, payload)
    return {"message": f"Successfully updated environment variables for service '{name}'"}
    
  @Command()
  def update_pod_label(self,
                 name: args.NAME,
                 setvar: args.SETVAR,
                 strategy: args.STRATEGY,
                 deletevar: args.DELETEVAR):
  
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
    if self.duplo.wait:
      service["Replicaset"] = self.current_replicaset(name)
      self.wait(service, payload)
    return {"message": f"Successfully updated pod labels for service '{name}'"}
  
  @Command()
  def bulk_update_image(self, 
                        serviceimage: args.SERVICEIMAGE) -> dict:
    """
    Bulk update the image of multiple services.

    Usage: Basic CLI Use
      ```sh
      duploctl service bulk_update_image -S <service-name-1> <image-name-1> -S <service-name-2> <image-name-2>
      ```

    Args:
      serviceimage: Takes n sets of two arguments, service name and image name. 
                    e.g., -S service1 image1:tag -S service2 image2:tag
      wait: Boolean flag to wait for service updates.
    """
    payload = []
    wait_list = []
    for name, image in serviceimage:
      service = self.find(name)
      payload_item = {
          "Name": name,
          "Image": image,
          "AllocationTags": service["Template"]["AllocationTags"]
      }
      payload.append(payload_item)
      if self.duplo.wait:
        wait_list.append({
          "old": service,
          "updated": payload_item
        })

    self.duplo.post(self.endpoint("ReplicationControllerBulkChangeAll"), payload)

    if self.duplo.wait:
      for update_info in wait_list:
        self.wait(**update_info)

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
      wait: Boolean flag to wait for service updates.

    Returns: 
      A success message if the service was restarted successfully.

    Raises:
      DuploError: If the service could not be restarted.
    """
    self.duplo.post(self.endpoint(f"ReplicationControllerReboot/{name}"))
    if self.duplo.wait:
      service = self.find(name)
      self.wait(service, service)
    return {"message": f"Successfully restarted service '{name}'"}
  
  @Command()
  def stop(self,
           name: args.NAME = None,
           all: args.ALL = False,
           targets: args.TARGETS = None) -> dict:
    """Stop a service.

    Stop a service.

    Usage: Basic CLI Use
      ```sh
      duploctl service stop <service-name>
      duploctl service stop --all
      duploctl service stop --targets service1 service2 service3
      ```

    Args:
      name (str): The name of the service to stop.
      all (bool): Boolean flag to stop all services. Defaults to False.
      targets (list[str]): List of service names to stop. Cannot be used with name or all.
      wait: Boolean flag to wait for service updates.

    Returns: 
      A summary containing services that were stopped successfully and those that encountered errors.
      
    Raises:
      DuploError: If the service could not be stopped.
    """
    return self._perform_action("Stop", name, all, targets, self.duplo.wait)

  @Command()
  def start(self,
            name: args.NAME = None,
            all: args.ALL = False,
            targets: args.TARGETS = None) -> dict:
    """Start a service.

    Start a service.

    Usage: Basic CLI Use
      ```sh
      duploctl service start <service-name>
      duploctl service start --all
      duploctl service start --targets service1 service2 service3
      ```
    
    Args:
      name (str): The name of the service to start.
      all (bool): Boolean flag to start all services. Defaults to False.
      targets (list[str]): List of service names to start. Cannot be used with name or all.
      wait: Boolean flag to wait for service updates.

    Returns: 
      A summary containing services that were started successfully and those that encountered errors.

    Raises:
      DuploError: If the service could not be started.
    """
    return self._perform_action("start", name, all, targets, self.duplo.wait)

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
           name: args.NAME) -> dict:
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
    if self.duplo.wait:
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
        raise DuploStillWaiting(f"Service {name} waiting for image update")
      if (replicas_changed and replicas != new_replicas):
        raise DuploStillWaiting(f"Service {name} waiting for replicas update")
      if (conf_changed and svc["Template"].get("OtherDockerConfig", None) != new_conf):
        raise DuploStillWaiting(f"Service {name} waiting for pod to update")
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
        raise DuploStillWaiting(f"Service {name} waiting for pods {running}/{replicas}")
      
    # send to the base class to do the waiting
    super().wait(wait_check, 3600, 11)

  def name_from_body(self, body):
    return body["Name"]

  @Command()
  def expose(self,
             name: args.NAME,
             container_port: args.CONTAINER_PORT=None,
             external_port: args.EXTERNAL_PORT=None,
             lb_type: args.LOAD_BALANCER_TYPE=None,
             protocol: args.PROTOCOL=None,
             visibility: args.LOAD_BALANCER_VISIBILITY="public",
             mode: args.LOAD_BALANCER_MODE="docker-mode",
             health_check_url: args.HEALTH_CHECK_URL=None) -> dict:
    """
    Expose a service.

    Usage: Basic CLI Use
      ```sh
      duploctl service expose <service-name> --lb-type applicationlb --container-port 80 --external-port 80  \
                             --visibility public --mode docker-mode --health-check-url / --protocol http
      ```

    Args:
        container-port (int): The internal port of the container to expose.
        external-port (int): The external port exposed by the load balancer. This is not used for targetgrouponly or k8clusterip load balancer types.
        lb-type (str): The load balancer type. Valid options are ['applicationlb', 'k8clusterip', 'k8nodeport', 'networklb', 'targetgrouponly'].
        protocol (str): The protocol to use, based on `lb_type`
          - applicationlb: http, https
          - networklb: tcp, udp, tls
          - targetgrouponly: http, https
          - k8clusterip: tcp, udp
          - k8nodeport: tcp, udp
        visibility (str): The load balancer visibility. Valid options are 'public' or 'private'.
        mode (str): The load balancer application mode. Valid options are 'docker-mode' or 'native-app'.
        health_check_url (str): The health check URL path. This must be empty for networklb, as it does not support health check paths.
    """
    service = self.find(name)
    tenant_id = service["TenantId"]
    lb_type_map = {
      "applicationlb": 1,
      "k8clusterip": 3,
      "k8nodeport": 4,
      "networklb": 6,
      "targetgrouponly": 7
    }

    if lb_type not in lb_type_map:
      raise DuploError(f"Invalid lb_type: {lb_type}. Must be one of {list(lb_type_map.keys())}")

    payload = {
        "LbType": lb_type_map[lb_type],
        "Port": container_port,
        "ExternalPort": external_port if external_port is not None else None,
        "IsInternal": visibility == "private",
        "IsNative": mode == "native-app",
        "Protocol": protocol,
        "HealthCheckUrl": health_check_url if lb_type != "networklb" else None,
        "ReplicationControllerName": name
    }

    self.duplo.post(f"subscriptions/{tenant_id}/LBConfigurationUpdate", payload)
    return {"message": f"Successfully exposed service '{name}'"}

  @Command()
  def rollback(self,
              name: args.NAME,
              to_revision: args.TO_REVISION = None) -> dict:
    """Rollback Service

    Roll back a service to a specific revision (if provided) or the last known good state.

    Usage:
      ```sh
      duploctl service rollback <service-name>
      duploctl service rollback <service-name> --to-revision 2
      ```

    Args:
        name (str): The name of the service to roll back.
        to_revision (int, optional): The revision number to roll back to.

    Returns:
        A success message indicating the rollback status.

    Raises:
      DuploError: If the service could not be rollback.
    """
    service = self.find(name)
    tenant_id = service["TenantId"]
    api_endpoint = f"v3/subscriptions/{tenant_id}/containers/replicationController/{name}/rollback"
    if to_revision:
      api_endpoint += f"/{to_revision}"
    self.duplo.put(api_endpoint)
    return {"message": f"Successfully rolled back service '{name}'"}