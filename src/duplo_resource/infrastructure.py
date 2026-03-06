from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploFailedResource, DuploStillWaiting
from duplocloud.resource import DuploResourceV2
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("infrastructure")
class DuploInfrastructure(DuploResourceV2):
  """Duplocloud Infrastructure Resource

  The infrastructure resource provides a set of commands to manage infrastructures in the Duplo system.
  An infrastructure defines the underlying cloud environment including VPC, subnets, and Kubernetes clusters.

  Usage: Basic CLI Use
    ```sh
    duploctl infrastructure <action>
    ```
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)

  @Command()
  def eks_config(self,
                 planId: args.PLAN = None):
    """EKS Configuration

    Retrieve EKS session credentials for the current user scoped to an infrastructure plan.

    Usage: Basic CLI Use
      ```sh
      duploctl infrastructure eks_config --plan <plan-name>
      ```

    Args:
      planId: The plan/infrastructure name to retrieve EKS config for.

    Returns:
      eks_config: The EKS cluster configuration and credentials.
    """
    res = self.client.get(f"v3/admin/plans/{planId}/k8sClusterConfig")
    return res.json()

  @Command()
  def list(self):
    """List Infrastructures

    Retrieve a list of all infrastructures in the Duplo system.

    Usage: Basic CLI Use
      ```sh
      duploctl infrastructure list
      ```

    Returns:
      infrastructures (list): A list of all infrastructures.
    """
    response = self.client.get("adminproxy/GetInfrastructureConfigs/true")
    return response.json()

  @Command()
  def find(self,
           name: args.NAME):
    """Find Infrastructure

    Find an infrastructure by name.

    Usage: Basic CLI Use
      ```sh
      duploctl infrastructure find <name>
      ```

    Args:
      name: The name of the infrastructure.

    Returns:
      infrastructure: The infrastructure object.
    """
    response = self.client.get(f"adminproxy/GetInfrastructureConfig/{name}")
    return response.json()

  @Command()
  def create(self,
             body: args.BODY):
    """Create Infrastructure

    Create a new infrastructure. When used with the `--wait` flag, the command will poll until the infrastructure reaches a `Complete` provisioning status.

    Usage: Basic CLI Use
      ```sh
      duploctl infrastructure create --file infra.yaml
      ```

    Example: Infrastructure Body
      Contents of the `infra.yaml` file
      ```yaml
      --8<-- "src/tests/data/infrastructure.yaml"
      ```

    Example: Create One Liner
      ```sh
      echo \"\"\"
      --8<-- "src/tests/data/infrastructure.yaml"
      \"\"\" | duploctl infrastructure create -f -
      ```

    Args:
      body: The infrastructure configuration body.

    Returns:
      message: A success message.
    """
    status = None
    name = body["Name"]
    def wait_check():
      nonlocal status
      i = self.find(name)
      s = i.get("ProvisioningStatus", "submitted")
      if status != s:
        self.duplo.logger.warn(f"Infrastructure '{name}' - {s}")
        status = s
      if s != "Complete":
        # stop waiting if the status contains failed
        if "Failed" in s:
          raise DuploFailedResource(f"Infrastructure '{name} - {s}'")
        raise DuploStillWaiting(f"Infrastructure '{name}' is waiting for status Complete")
    self.client.post("adminproxy/CreateInfrastructureConfig", body)
    if self.duplo.wait:
      self.wait(wait_check, 1800, 20)
    return {
      "message": f"Infrastructure '{body['Name']}' created"
    }

  @Command()
  def delete(self,
             name: args.NAME):
    """Delete Infrastructure

    Delete an infrastructure by name.

    Usage: Basic CLI Use
      ```sh
      duploctl infrastructure delete <name>
      ```

    Args:
      name: The name of the infrastructure to delete.

    Returns:
      message: A success message.
    """
    self.client.post(f"adminproxy/DeleteInfrastructureConfig/{name}", None)
    return {
      "message": f"Infrastructure '{name}' deleted"
    }

  @Command()
  def faults(self,
             name: args.NAME):
    """Infrastructure Faults

    Retrieve a list of all faults across infrastructures in the Duplo system.

    Usage: Basic CLI Use
      ```sh
      duploctl infrastructure faults <name>
      ```

    Args:
      name: The name of the infrastructure.

    Returns:
      faults (list): A list of infrastructure faults.
    """
    response = self.client.get("adminproxy/GetAllFaults")
    faults = response.json()
    response = self.client.get("admin/GetAllFaults")
    faults += response.json()
    return faults
