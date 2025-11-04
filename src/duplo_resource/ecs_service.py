from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV2
from duplocloud.errors import DuploError, DuploStillWaiting
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("ecs")
class DuploEcsService(DuploTenantResourceV2):
  """Manage Duplo ECS Resources
  
  A collection of commands to manage ECS services and task definitions.
  
  """

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)

  @Command()
  def list_services(self) -> list:
    """List ECS Services

    Retrieve a list of all ECS services in a tenant.
    
    Usage: CLI Usage
      ```sh
      duploctl ecs list_services
      ```

    Returns:
      list: A list of ECS services in the tenant.
    """
    tenant_id = self.tenant["TenantId"]
    url = f"subscriptions/{tenant_id}/GetEcsServices"
    response = self.duplo.get(url)
    return response.json()

  @Command()
  def find_service_family(self,
                          name: args.NAME):
    """Find Service Family by Name
    
    Find an ECS Services task definition family by name.

    Args:
      name: The name of the ECS task definition to find.

    Returns:
      task_definition_family: The ECS task definition object.

    Raises:
      DuploError: If the ECS task definition could not be found.
    """
    tenant_id = self.tenant["TenantId"]
    path = f"v3/subscriptions/{tenant_id}/aws/ecs/service/taskDefFamily/{name}"
    response = self.duplo.get(path)
    return response.json()

  @Command()
  def delete_service(self,
                     name: args.NAME) -> dict:
    """Delete an ECS service.

    Args:
      name: The name of the ECS service to delete.

    Returns:
      message: A message indicating the service has been deleted.
    """
    tenant_id = self.tenant["TenantId"]
    path = f"subscriptions/{tenant_id}/DeleteEcsService/{name}"
    response = self.duplo.post(path, {})
    return response.json()

  @Command()
  def list_task_def_family(self) -> dict:
    """List ECS Task Definitions

    Retrieve a list of all ECS task definitions in a tenant.

    Example:
      CLI usage
      ```sh
      duploctl ecs list_definitions
      ```

    Returns:
      task_def_family: The historical list of ECS task definitions within a family.
    """
    tenant_id = self.tenant["TenantId"]
    path = f"v3/subscriptions/{tenant_id}/aws/ecs/taskDefFamily"
    response = self.duplo.get(path)
    return response.json()

  @Command()
  def find_def(self,
               name: args.NAME):
    """Find the latest version of an ECS task definition by family name.

    Args:
      name: The family name of the ECS task definition to find.

    Returns:
      task_definition: The latest version of that ECS task definition in the family.

    Raises:
      DuploError: If the ECS task definition could not be found.
    """
    name = self.prefixed_name(name)
    task_definition_family = self.find_task_def_family(name)
    arn = task_definition_family["VersionArns"][-1]
    return self.find_def_by_arn(arn)

  @Command()
  def find_def_by_arn(self,
                      arn: args.ARN) -> dict:
    """Find a ECS task definition by ARN.

    Find a task definition by its AWS ARN.

    Args:
      arn: The ARN of the ECS task definition to find.

    Returns:
      task_definition: The ECS task definition object.

    Raises:
      DuploError: If the ECS task definition could not be found.
    """
    path = self.endpoint("FindEcsTaskDefinition")
    response = self.duplo.post(path, {"Arn": arn})
    return response.json()

  @Command()
  def find_task_def_family(self,
                           name: args.NAME):
    """Find a ECS task definition family by name.

    Args:
      name: The name of the ECS task definition to find.

    Returns:
      The ECS task definition object.

    Raises:
      DuploError: If the ECS task definition could not be found.
    """
    name = self.prefixed_name(name)
    tenant_id = self.tenant["TenantId"]
    path = f"v3/subscriptions/{tenant_id}/aws/ecs/taskDefFamily/{name}"
    response = self.duplo.get(path)
    return response.json()

  @Command()
  def update_service(self,
             body: args.BODY) -> dict:
    """Update an ECS service.

    Args:
      body (dict): The updated ECS service object.

    Returns:
      message: A success message. 

    Raises:
      DuploError: If the ECS service could not be updated.
    """
    path = self.endpoint("UpdateEcsService")
    self.duplo.post(path, body)
    return {"message": "ECS Service updated"}

  @Command()
  def update_taskdef(self,
                     body: args.BODY) -> dict:
    """Update an ECS task definition.

    Updates a task definition. This creates a new revision of the task definition and returns the new ARN.
    Note each definition is immutable so this is effectively a create operation for one item in a set and the latest one is the active one.

    Args:
      body: The updated ECS task definition object.

    Returns:
      task_definition: The updated ECS task definition object.

    Raises:
      DuploError: If the ECS task definition could not be updated.
    """
    path = self.endpoint("UpdateEcsTaskDefinition")
    b = self.__ecs_task_def_body(body)
    response = self.duplo.post(path, b)
    return {"arn": response.json()}

  @Command()
  def update_image(self,
                   name: args.NAME,
                   image: args.IMAGE = None,
                   container_image: args.CONTAINER_IMAGE = None) -> dict:
    """Update Image
    
    Creates a new task definition version cloning the latest existing version in the family except for image arguments

    If task family is used by an ECS service, method also updates the service to use that newly created definition version

    Usage: Basic CLI Use
      ```sh
        duploctl ecs update_image <task-definition-family-name> <new-image>
      ```
      ```sh
        duploctl ecs update_image <task-definition-family-name> --container-image <container-name> <new-container-image>
      ```

    Example: Update image and wait
      This supports the global `--wait` flag to hold the terminal until the service update is complete.
      Waits for the status of the service to be the desired running status. 
      ```sh
        duploctl ecs update_image myapp myimage:latest --wait
      ```

    Args:
      name: The name of the ECS task definition family to update.
      image: The new image to use for the container.
      container-image: A list of key-value pairs to set as container image.

    Returns:
      dict: A dictionary containing a message about the update status.

    Raises:
      DuploError: If the ECS task definition family could not be updated.
    """
    name = self.prefixed_name(name)
    tdf = self.find_def(name)
    if container_image:
      container_updates = dict(container_image)
      for container_def in tdf["ContainerDefinitions"]:
        if container_def["Name"] in container_updates:
          container_def["Image"] = container_updates[container_def["Name"]]
    if image:
      tdf["ContainerDefinitions"][0]["Image"] = image
    arn = self.update_taskdef(tdf)["arn"]
    msg = "Updating a task definition and its corresponding service."
    svc = None
    try:
      svcFam = self.find_service_family(name)
      svc = svcFam["DuploEcsService"]
      svc["TaskDefinition"] = arn
    except DuploError:
      msg = "No Service Configured, only the definition is updated."
    # run update here so the errors bubble up correctly
    if svc:
      self.update_service(svc)
      if self.duplo.wait:
        self.wait(lambda: self.wait_on_task(name))
    return {
      "message": msg
    }

  def __ecs_task_def_body(self, task_def):
    def sanitize_container_definition(containerDefinition):
        if containerDefinition.get("Cpu") == 0:
          del containerDefinition["Cpu"]
        if containerDefinition.get("Memory") == 0:
          del containerDefinition["Memory"]
        if containerDefinition.get("MemoryReservation") == 0:
          del containerDefinition["MemoryReservation"]
        if containerDefinition.get("StartTimeout") == 0:
          del containerDefinition["StartTimeout"]
        if containerDefinition.get("StopTimeout") == 0:
          del containerDefinition["StopTimeout"]
        return containerDefinition
    
    containers = list(map(sanitize_container_definition, task_def.get("ContainerDefinitions", [])))

    def sanitize_volume(v):
      if "EfsVolumeConfiguration" in v and "TransitEncryptionPort" in v["EfsVolumeConfiguration"] and v["EfsVolumeConfiguration"]["TransitEncryptionPort"] == 0:
        del v["EfsVolumeConfiguration"]["TransitEncryptionPort"]
      return v

    result = {
      "Family": task_def["Family"],
      "InferenceAccelerators": task_def.get("InferenceAccelerators", []),
      "NetworkMode": task_def.get("NetworkMode", {}),
      "ContainerDefinitions": containers,
      "RuntimePlatform": task_def.get("RuntimePlatform", {}),
      "RequiresCompatibilities": task_def.get("RequiresCompatibilities", []),
      "Volumes": list(map(sanitize_volume, task_def.get("Volumes", []))),
    }
    if task_def.get("Cpu") not in (None, 0):
      result["Cpu"] = task_def["Cpu"]
    if task_def.get("Memory") not in (None, 0):
      result["Memory"] = task_def["Memory"]
    if task_def.get("MemoryReservation") not in (None, 0):
      result["MemoryReservation"] = task_def["MemoryReservation"]
    if "EphemeralStorage" in task_def:
      result["EphemeralStorage"] = task_def["EphemeralStorage"]
    if "ExecutionRoleArn" in task_def:
      result["ExecutionRoleArn"] = task_def["ExecutionRoleArn"]
    if "IpcMode" in task_def:
      result["IpcMode"] = task_def["IpcMode"]
    if "PlacementConstraints" in task_def:
      result["PlacementConstraints"] = task_def["PlacementConstraints"]
    if "ProxyConfiguration" in task_def:
      result["ProxyConfiguration"] = task_def["ProxyConfiguration"]
    if "TaskRoleArn" in task_def:
      result["TaskRoleArn"] = task_def["TaskRoleArn"]

    return result

  @Command()
  def list_tasks(self,
                 name: args.NAME) -> list:
    """List Tasks
    
    List ECS tasks given a name.

    Usage: Basic CLI Use
      ```sh
      duploctl ecs list_tasks <service-name>
      ```

    Args:
      name: The name of the ECS service to list tasks for.

    Returns:
      list: A list of ECS tasks associated with the service.
    """
    tenant_id = self.tenant["TenantId"]
    path = f"v3/subscriptions/{tenant_id}/aws/ecsTasks/{name}"
    res = self.duplo.get(path)
    return res.json()

  @Command()
  def run_task(self,
               name: args.NAME,
               replicas: args.REPLICAS) -> dict:
    """Run a task from an ECS task definition family's latest definition version."

    Execute a task based on some definition.

    Usage: Basic CLI Use
      ```sh
      duploctl ecs run_task <task-definition-family-name> <replicas>
      ```

    Example: Wait for task to complete
      This supports the global `--wait` flag to hold the terminal until the task is complete.
      Waits for the status of the task to be the desired complete status.
      ```sh
      duploctl ecs run_task myapp 3 --wait
      ```

    Args:
      name: The name of the ECS task definition family the task will be spawned from.
      replicas: The number of replicas to run.

    Returns:
      message: A message indicating the task has been run.
    """
    td = self.find_def(name)
    tenant_id = self.tenant["TenantId"]
    path = f"v3/subscriptions/{tenant_id}/aws/runEcsTask"
    body = {
      "TaskDefinition": td["TaskDefinitionArn"],
      "Count": replicas if replicas else 1
    }
    res = self.duplo.post(path, body)
    if self.duplo.wait:
      self.wait(lambda: self._wait_on_task(name))
    return res.json()

  def _wait_on_task(self,
                   name: str) -> None:
    tasks = self.list_tasks(name)
    # filter the tasks down to any where the DesiredStatus and LastStatus are different
    running_tasks = [t for t in tasks if t["DesiredStatus"] != t["LastStatus"]]
    if len(running_tasks) > 0:
      raise DuploStillWaiting(f"Service {name} waiting for replicas update")
