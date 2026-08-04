from urllib.parse import quote_plus

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploNotFound
from duplocloud.commander import Command, Resource
from duplo_resource.helpdesk import HelpdeskResource
from duplo_resource.helpdesk_client import unwrap_data, unwrap_items
import duplocloud.args as args


@Resource("hd_lambda", scope="workspace", client="helpdesk")
class DuploHelpdeskLambda(HelpdeskResource):
  """Manage AI HelpDesk (HDV2) AWS Lambda functions in DuploCloud.

  This is the HelpDesk V2 equivalent of the Core Platform ``lambda``
  resource. Lambdas live inside a workspace, under an
  environment/resource-group; ``find``/``list``/``update_image`` operate
  at the workspace scope, while ``create``/``update``/``delete`` use the
  nested environment/resource-group scope. Environment and
  resource-group resolution are delegated to their respective resources
  via the shared :class:`HelpdeskResource` helpers; the workspace comes
  from the global ``-W``/``--workspace-id`` flags.
  """

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)

  def _base(self) -> str:
    """Build the workspace-scoped AwsLambdas endpoint."""
    return (f"user/data/workspaces/{self.workspace_id}/"
            f"environment/AwsLambdas")

  def _nested_base(self,
                   environment_id: str,
                   resource_group_id: str) -> str:
    """Build the env/resource-group-scoped AwsLambdas endpoint."""
    return (f"user/data/workspaces/{self.workspace_id}/environments/"
            f"{quote_plus(environment_id)}/resource-groups/"
            f"{quote_plus(resource_group_id)}/AwsLambdas")

  @Command("ls")
  def list(self) -> list:
    """Retrieve the AWS Lambdas in an AI HelpDesk workspace.

    Usage: CLI Usage
      ```sh
      duploctl hd_lambda list -W <workspace>
      duploctl hd_lambda list --workspace-id <workspace id>
      ```

    Returns:
      list: The lambdas in the workspace.
    """
    response = self.client.get(self._base()).json()
    return unwrap_items(response)

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None) -> dict:
    """Find an AI HelpDesk AWS Lambda by name or id within a workspace.

    Usage: CLI Usage
      ```sh
      duploctl hd_lambda find <name> -W <workspace>
      duploctl hd_lambda find --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The lambda name as shown in the portal.
      id: The lambda id. Skips the name lookup when provided.

    Returns:
      resource: The matching lambda object.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no lambda matches the name or id.
    """
    return self._find_in_workspace(name, id)

  @Command()
  def create(self,
             body: args.BODY,
             environment: args.ENVIRONMENT = None,
             environment_id: args.ENVIRONMENTID = None,
             resource_group: args.RESOURCEGROUP = None,
             resource_group_id: args.RESOURCEGROUPID = None) -> dict:
    """Create an AI HelpDesk AWS Lambda under an environment/resource group.

    The lambda is created on the nested environment/resource-group route,
    which the backend uses to stamp the placement onto the spec. The
    environment and resource group are resolved by name or id via their
    respective resources.

    Usage: CLI Usage
      ```sh
      duploctl hd_lambda create -f lambda.yaml -W <workspace> --environment <env> --resource-group <rg>
      ```

    Args:
      body: The lambda definition.
      environment: The environment name to create the lambda in.
      environment_id: The environment id. Skips the environment lookup.
      resource_group: The resource group name to create the lambda in.
      resource_group_id: The resource group id. Skips the lookup.

    Returns:
      resource: The created lambda object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the environment or resource group is not found.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    eid, rgid = self._resolve_env_rg(
        environment, environment_id, resource_group, resource_group_id)
    response = self.client.post(self._nested_base(eid, rgid), body).json()
    return unwrap_data(response)

  @Command()
  def update(self,
             body: args.BODY = None,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Update an AI HelpDesk AWS Lambda.

    The target is resolved by ``--id``, ``name``, or the body's ``name``
    field, in that order. The environment/resource-group ids are read off
    the existing record to build the nested update route.

    Usage: CLI Usage
      ```sh
      duploctl hd_lambda update <name> -f lambda.yaml -W <workspace>
      duploctl hd_lambda update -f lambda.yaml -W <workspace>
      ```

    Args:
      body: The lambda definition to apply.
      name: The lambda name. Defaults to the body's ``name``.
      id: The lambda id. Skips the name lookup when provided.

    Returns:
      resource: The updated lambda object.

    Raises:
      DuploError: If no body is provided.
      DuploNotFound: If the lambda cannot be found.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    fn = self._find_in_workspace(name or body.get("name"), id)
    lid = self._id_of(fn)
    eid, rgid = self._record_env_rg(fn)
    # The backend rejects the PUT as a self name-collision unless the body
    # carries its own id, matching the workspace/agent update contract.
    body = {**body, "id": lid}
    response = self.client.put(
        f"{self._nested_base(eid, rgid)}/{quote_plus(lid)}", body).json()
    return unwrap_data(response)

  @Command()
  def apply(self,
            body: args.BODY,
            environment: args.ENVIRONMENT = None,
            environment_id: args.ENVIRONMENTID = None,
            resource_group: args.RESOURCEGROUP = None,
            resource_group_id: args.RESOURCEGROUPID = None) -> dict:
    """Create or update an AI HelpDesk AWS Lambda.

    Looks the lambda up by the body's ``name``: updates it when it
    exists, creates it otherwise. The environment/resource-group
    selectors are only used on the create path.

    Usage: CLI Usage
      ```sh
      duploctl hd_lambda apply -f lambda.yaml -W <workspace> --environment <env> --resource-group <rg>
      ```

    Args:
      body: The lambda definition to apply.
      environment: The environment name (used when creating).
      environment_id: The environment id (used when creating).
      resource_group: The resource group name (used when creating).
      resource_group_id: The resource group id (used when creating).

    Returns:
      resource: The created or updated lambda object.

    Raises:
      DuploError: If no body is provided or it has no ``name``.
    """
    if not isinstance(body, dict):
      raise DuploError("A request body (-f) is required")
    if not body.get("name"):
      raise DuploError("The body must include a 'name'")
    try:
      self._find_in_workspace(body.get("name"), None)
    except DuploNotFound:
      return self.create(
          body=body, environment=environment, environment_id=environment_id,
          resource_group=resource_group, resource_group_id=resource_group_id)
    return self.update(body=body)

  @Command()
  def delete(self,
             name: args.NAME = None,
             id: args.ID = None) -> dict:
    """Deprovision an AI HelpDesk AWS Lambda.

    Initiates deprovisioning on the nested environment/resource-group
    route (the HelpDesk V2 teardown for a workload); the ids are read off
    the existing record.

    Usage: CLI Usage
      ```sh
      duploctl hd_lambda delete <name> -W <workspace>
      duploctl hd_lambda delete --id <id> --workspace-id <workspace id>
      ```

    Args:
      name: The lambda name as shown in the portal.
      id: The lambda id. Skips the name lookup when provided.

    Returns:
      message: A success message.

    Raises:
      DuploNotFound: If the lambda cannot be found.
    """
    fn = self._find_in_workspace(name, id)
    lid = self._id_of(fn)
    eid, rgid = self._record_env_rg(fn)
    self.client.post(
        f"{self._nested_base(eid, rgid)}/{quote_plus(lid)}/deprovision")
    return {"message": f"lambda '{name or id}' deprovisioning initiated"}

  @Command()
  def update_image(self,
                   name: args.NAME,
                   image: args.IMAGE) -> dict:
    """Update the container image of an AI HelpDesk AWS Lambda.

    A container-image Lambda code update is a passthrough to AWS Lambda's
    ``UpdateFunctionCode`` API. The lambda is resolved to its id within
    the workspace, and its environment/resource-group ids are read off
    the record to build the nested code-update endpoint. The function
    identifier is stamped server-side, so only the image is sent.

    Usage: CLI Usage
      ```sh
      duploctl hd_lambda update_image <name> <image> -W <workspace>
      ```

    Args:
      name: The name of the lambda to update.
      image: The new container image (ECR ImageUri).

    Returns:
      resource: The updated lambda object.

    Raises:
      DuploError: If no image is given, the workspace cannot be resolved,
        or the lambda's environment/resource-group cannot be determined.
      DuploNotFound: If the lambda cannot be found.
    """
    if not image or not image.strip():
      raise DuploError("An image is required")
    fn = self._find_in_workspace(name, None)
    lid = self._id_of(fn)
    eid, rgid = self._record_env_rg(fn)
    # The code-update route is nested under env/resource-group even though
    # the lambda was listed at the workspace scope; the AWS SDK request body
    # only needs the new ImageUri (FunctionName is stamped server-side).
    path = f"{self._nested_base(eid, rgid)}/{quote_plus(lid)}/code"
    response = self.client.post(path, {"ImageUri": image}).json()
    return unwrap_data(response)
