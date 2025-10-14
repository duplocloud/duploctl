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
    """Find a ECS task definition by name.

    Args:
      name: The name of the ECS task definition to find.

    Returns:
      task_definition: The ECS task definition object.

    Raises:
      DuploError: If the ECS task definition could not be found.
    """
    name = self.prefixed_name(name)
    svcFam = self.find_service_family(name)
    family = svcFam["TaskDefFamily"]
    tdf = self.find_task_def_family(family)
    arn = tdf["VersionArns"][-1]
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
    
    Update the image for an ECS task definition and service container if one exists.

    Usage: Basic CLI Use
      ```sh
        duploctl ecs update_image <service-name> <service-image>
      ```
      ```sh
        duploctl ecs update_image <service-name> --container-image <container-name> <container-image>
      ```

    Example: Update image and wait
      This supports the global `--wait` flag to hold the terminal until the service update is complete.
      Waits for the status of the service to be the desired running status. 
      ```sh
        duploctl ecs update_image myapp myimage:latest --wait
      ```

    Args:
      name: The name of the ECS service to update.
      image: The new image to use for the container.
      container-image: A list of key-value pairs to set as container image.

    Returns:
      dict: A dictionary containing a message about the update status.

    Raises:
      DuploError: If the ECS service could not be updated.
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
    containers = [
      self.__ecs_container_update_body(c)
      for c in task_def.get("ContainerDefinitions", [])
    ]
    result = {
      "Family": task_def["Family"],
      "InferenceAccelerators": task_def.get("InferenceAccelerators", []),
      "NetworkMode": task_def.get("NetworkMode", {}),
      "ContainerDefinitions": containers,
      "RuntimePlatform": task_def.get("RuntimePlatform", {})
    }
    if task_def.get("Cpu") not in (None, 0):
      result["Cpu"] = task_def["Cpu"]
    if task_def.get("Memory") not in (None, 0):
      result["Memory"] = task_def["Memory"]
    if task_def.get("MemoryReservation") not in (None, 0):
      result["MemoryReservation"] = task_def["MemoryReservation"]
    return result


  def __ecs_container_update_body(self, container_def):
    update_body = {
        "Essential": container_def.get("Essential"),
        "Image": container_def.get("Image") ,
        "Name": container_def.get("Name") ,
        "PortMappings": container_def.get("PortMappings", []) ,
        "Environment": container_def.get("Environment", {}) ,
        "Command": container_def.get("Command", {}) ,
        "Secrets": container_def.get("Secrets", {}) ,
        "EnvironmentFiles": container_def.get("EnvironmentFiles", {})
    }

    # Add LogConfiguration only if it exists in container_def
    if "LogConfiguration" in container_def:
        update_body["LogConfiguration"] = container_def["LogConfiguration"]
    # Add FirelensConfiguration only if it exists in container_def
    if "FirelensConfiguration" in container_def:
        update_body["FirelensConfiguration"] = container_def["FirelensConfiguration"]
    if container_def.get("Cpu") not in (None, 0):
        update_body["Cpu"] = container_def["Cpu"]
    if container_def.get("Memory") not in (None, 0):
        update_body["Memory"] = container_def["Memory"]
    if container_def.get("MemoryReservation") not in (None, 0):
        update_body["MemoryReservation"] = container_def["MemoryReservation"]
    if container_def.get("RepositoryCredentials") not in (None, 0):
        update_body["RepositoryCredentials"] = container_def["RepositoryCredentials"]
    return update_body

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
    """Run a task for an ECS service."

    Execute a task based on some definition.

    Usage: Basic CLI Use
      ```sh
      duploctl ecs run_task <service-name> <replicas>
      ```

    Example: Wait for task to complete
      This supports the global `--wait` flag to hold the terminal until the task is complete.
      Waits for the status of the task to be the desired complete status.
      ```sh
      duploctl ecs run_task myapp 3 --wait
      ```

    Args:
      name: The name of the ECS service to run the task for.
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
