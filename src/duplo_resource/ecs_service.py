from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("ecs")
class DuploEcsService(DuploTenantResource):

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)

  @Command()
  def list(self):
    """Retrieve a list of all ECS services in a tenant."""
    tenant_id = self.tenant["TenantId"]
    url = f"subscriptions/{tenant_id}/GetEcsServices"
    response = self.duplo.get(url)
    return response.json()
  
  @Command()
  def find(self, 
           name: args.NAME):
    """Find a ECS service by name.

    Args:
      name (str): The name of the ECS service to find.
    Returns:
      The ECS service object.
    Raises:
      DuploError: If the ECS service could not be found.
    """
    try:
      return [s for s in self.list() if s["Name"] == name][0]
    except IndexError:
      raise DuploError(f"ECS Service '{name}' not found", 404)
  
  @Command()
  def list_task_def_family(self):
    """List ECS Task Definitions
    
    Retrieve a list of all ECS task definitions in a tenant.

    Example: 
      CLI usage  
      ```sh  
      duploctl ecs list_definitions
      ```

    Returns:
      A list of ECS task definitions.
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
      name (str): The name of the ECS task definition to find.
    Returns:
      The ECS task definition object.
    Raises:
      DuploError: If the ECS task definition could not be found.
    """
    tdf = self.find_task_def_family(name)
    arn = tdf["VersionArns"][-1]
    return self.find_def_by_arn(arn)
  
  @Command()
  def find_def_by_arn(self, 
                      arn: args.ARN):
    """Find a ECS task definition by ARN.

    Args:
      arn (str): The ARN of the ECS task definition to find.
    Returns:
      The ECS task definition object.
    Raises:
      DuploError: If the ECS task definition could not be found.
    """
    tenant_id = self.tenant["TenantId"]
    path = f"subscriptions/{tenant_id}/FindEcsTaskDefinition"
    response = self.duplo.post(path, {"Arn": arn})
    return response.json()
      
  @Command()
  def find_task_def_family(self, 
                           name: args.NAME):
    """Find a ECS task definition by name.

    Args:
      name (str): The name of the ECS task definition to find.
    Returns:
      The ECS task definition object.
    Raises:
      DuploError: If the ECS task definition could not be found.
    """
    tenant_id = self.tenant["TenantId"]
    path = f"v3/subscriptions/{tenant_id}/aws/ecs/taskDefFamily/{name}"
    response = self.duplo.get(path)
    return response.json()
  
  @Command()
  def update(self, 
             body: args.BODY):
    """Update an ECS service.

    Args:
      body (dict): The updated ECS service object.
    Returns:
      The updated ECS object.
    Raises:
      DuploError: If the ECS service could not be updated.
    """
    tenant_id = self.tenant["TenantId"]
    path = f"subscriptions/{tenant_id}/UpdateEcsService"
    self.duplo.post(path, body)
    return {"message": "ECS Service updated"}
  
  @Command()
  def update_taskdef(self, 
                     body: args.BODY):
    """Update an ECS task definition.

    Args:
      body (dict): The updated ECS task definition object.
    Returns:
      The updated ECS object.
    Raises:
      DuploError: If the ECS task definition could not be updated.
    """
    tenant_id = self.tenant["TenantId"]
    path = f"subscriptions/{tenant_id}/UpdateEcsTaskDefinition"
    b = self.__ecs_task_def_body(body)
    response = self.duplo.post(path, b)
    return {"arn": response.json()}

  @Command()
  def update_image(self, 
                   name: args.NAME, 
                   image: args.IMAGE):
    """Update the image for an ECS service.

    Example:
      CLI usage
      ```sh
      duploctl ecs update_image my-service my-image
      ```

    Args:
      name (str): The name of the ECS service to update.
      task_definition (str): The new task definition to use.
    Returns:
      The updated ECS object.
    Raises:
        DuploError: If the ECS service could not be updated.
    """
    svc = self.find(name)
    tdf = self.find_def_by_arn(svc["TaskDefinition"])
    tdf["ContainerDefinitions"][0]["Image"] = image
    arn = self.update_taskdef(tdf)["arn"]
    svc["TaskDefinition"] = arn
    return self.update(svc)

  def __ecs_task_def_body(self, task_def):
    containers = [
      self.__ecs_container_update_body(c) 
      for c in task_def.get("ContainerDefinitions", [])]
    return {
      "Family": task_def["Family"],
      "Cpu": task_def["Cpu"],
      "Memory": task_def["Memory"],
      "InferenceAccelerators": task_def.get("InferenceAccelerators", []),
      "NetworkMode": task_def.get("NetworkMode", {}),
      "ContainerDefinitions": containers
    }
  
  def __ecs_container_update_body(self, container_def):
    return {
      "Essential": container_def["Essential"],
      "Image": container_def["Image"],
      "Name": container_def["Name"],
      "PortMappings": container_def.get("PortMappings", []),
      "LogConfiguration": container_def.get("LogConfiguration", {}),
    }
