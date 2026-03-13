from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploFailedResource, DuploStillWaiting
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

    Raises:
      DuploNotFound: If the infrastructure does not exist. Raised by the
        HTTP client layer when the API returns a 404 response.
    """
    response = self.client.get(f"adminproxy/GetInfrastructureConfig/{name}")
    return response.json()
  
  _INFRA_FAULT_TENANTS = {"System.VPC", "System.AwsInfrastructure"}

  def _faults_for(self, name: str) -> list:
    """Return faults relevant to the named infrastructure.

    Includes faults where Resource.Name matches the infra name directly,
    plus generic system-level faults from infrastructure-related modules
    (System.VPC, System.AwsInfrastructure) that have no specific resource name.
    """
    try:
      all_faults = self.faults(name)
    except Exception:
      return []
    return [
      f for f in all_faults
      if f.get("Resource", {}).get("Name") == name
      or (
        f.get("TenantId") in self._INFRA_FAULT_TENANTS
        and f.get("Resource", {}).get("Name") == "Generic"
      )
    ]

  @Command(model="Infrastructure")
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
        self.duplo.logger.warning(f"Infrastructure '{name}' - {s}")
        status = s
      if s != "Complete":
        # stop waiting if the status contains failed
        if "Failed" in s:
          fault_descs = [
            f.get("Description", "")
            for f in self._faults_for(name)
            if f.get("Description")
          ]
          detail = (" | Faults: " + "; ".join(fault_descs)) if fault_descs else ""
          raise DuploFailedResource(f"Infrastructure '{name}' - {s}{detail}")
        raise DuploStillWaiting(f"Infrastructure '{name}' is waiting for status Complete")
    self.client.post("adminproxy/CreateInfrastructureConfig", body)
    if self.duplo.wait:
      self.wait(wait_check, 1800, 20)
    return {
      "message": f"Infrastructure '{body['Name']}' created"
    }

  @Command()
  def update(self,
             name: args.NAME,
             body: args.BODY = None) -> dict:
    """Update Infrastructure

    Infrastructure fields are immutable after creation; this command
    validates that the caller is not attempting to change any field and
    returns a success message when the infrastructure already exists with
    the expected configuration.

    Usage: Basic CLI Use
      ```sh
      duploctl infrastructure update <name> --file infra.yaml
      ```

    Args:
      name: The name of the infrastructure.
      body: The infrastructure configuration body (used only for
        immutability validation; no API update is performed).

    Returns:
      message: A success message indicating the infrastructure exists.

    Raises:
      DuploNotFound: If the infrastructure does not exist. This is raised
        by ``find()`` via the HTTP client layer on a 404 response, and
        intentionally allowed to bubble up so that ``apply()`` can catch
        it and branch to ``create()`` instead.
      DuploError: If any fields in the body differ from the existing
        infrastructure (all fields are immutable).
    """
    # find() raises DuploNotFound automatically when the infra is absent,
    # so no explicit try/catch is needed here — the error bubbles up to
    # apply() which catches DuploNotFound to decide create vs update.
    existing = self.find(name)
    self.duplo.logger.warning(
      f"Infrastructure '{name}' fields are immutable; "
      "no update will be performed."
    )
    if body:
      changed = [
        k for k, v in body.items()
        if k in existing and existing[k] != v
      ]
      if changed:
        raise DuploError(
          f"Infrastructure '{name}' fields are immutable and cannot be "
          f"updated: {', '.join(changed)}",
          422,
        )
    return {
      "message": f"Infrastructure '{name}' already exists (no-op update)"
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
