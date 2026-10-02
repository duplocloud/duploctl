"""AI HelpDesk AWS just-in-time credentials.

Read-only workspace-scoped resource that mints temporary AWS
credentials from the AI HelpDesk — the helpdesk counterpart to the
core platform's ``jit aws``. Two backend routes serve it: a cloud
scope (``user/data/workspaces/{wid}/scopes/{sid}/aws/jitAccess``) or a
resource group (``.../environments/{eid}/resource-groups/{rgid}/aws/
jitAccess``); both return the same credential contract.
"""
from urllib.parse import quote_plus

from duplocloud.commander import Command, Resource
from duplocloud.errors import DuploError
from duplo_resource.helpdesk import HelpdeskResource
from duplo_resource.helpdesk_client import unwrap_data
import duplocloud.args as args


@Resource("aws_credentials", scope="workspace", client="helpdesk")
class DuploAwsCredentials(HelpdeskResource):
  """Mint just-in-time AWS credentials from an AI HelpDesk.

  Read-only: returns temporary STS credentials (access key, secret,
  session token), the region, expiry, and a federated AWS Console
  sign-in URL. Credentials are minted per call and expire; nothing is
  created or stored.
  """

  def _workspace_base(self) -> str:
    """Build the workspace-scoped user data-plane prefix."""
    return f"user/data/workspaces/{quote_plus(self.workspace_id)}"

  @Command("ls")
  def list(self) -> list:
    """List the AWS cloud scopes available in the workspace.

    These are the scope targets ``find`` can mint credentials for.

    Usage: CLI Usage
      ```sh
      duploctl aws_credentials list -W <workspace>
      ```

    Returns:
      resources: The workspace's AWS cloud scopes.
    """
    response = self.client.get(
        f"{self._workspace_base()}/scopes?providerTypes=AWS").json()
    data = response.get("data")
    return data if isinstance(data, list) else []

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None,
           resource_group: args.RESOURCEGROUP = None,
           resource_group_id: args.RESOURCEGROUPID = None,
           environment: args.ENVIRONMENT = None,
           environment_id: args.ENVIRONMENTID = None) -> dict:
    """Mint JIT AWS credentials for a cloud scope or resource group.

    Without a resource group the credentials come from a cloud scope:
    pass the scope ``name`` (or ``--id``), or omit both when the
    workspace has exactly one AWS scope. With ``--resource-group`` (or
    ``--resource-group-id``) the credentials come from the IAM role
    attached to that resource group instead; the environment is
    resolved from the resource group record.

    Usage: CLI Usage
      ```sh
      duploctl aws_credentials find <scope name> -W <workspace>
      duploctl aws_credentials find --rg <resource group> -W <workspace>
      duploctl aws_credentials find -W <workspace> -q '{
        AWS_ACCESS_KEY_ID: accessKeyId,
        AWS_SECRET_ACCESS_KEY: secretAccessKey,
        AWS_SESSION_TOKEN: sessionToken,
        AWS_REGION: region}' -o env
      ```

    Args:
      name: The cloud scope name. Optional when the workspace has
        exactly one AWS scope.
      id: The cloud scope id. Skips the scope name lookup.
      resource_group: Mint for this resource group (by name) instead
        of a scope.
      resource_group_id: The resource group id. Skips the name lookup.
      environment: Disambiguate the resource group name lookup by
        environment name.
      environment_id: Disambiguate the resource group name lookup by
        environment id.

    Returns:
      credentials: The temporary access key id, secret access key,
        session token, region, validity, expiration, and federated
        console URL.

    Raises:
      DuploError: If no scope matches, the selection is ambiguous, or
        the AI HelpDesk returns no credentials.
      DuploNotFound: If the resource group cannot be found.
    """
    if resource_group or resource_group_id:
      path = self._resource_group_path(
          resource_group, resource_group_id, environment, environment_id)
    else:
      sid = id or self._scope_id(name)
      path = f"{self._workspace_base()}/scopes/{quote_plus(sid)}/aws/jitAccess"
    creds = unwrap_data(self.client.post(path).json())
    if not isinstance(creds, dict) or not creds.get("accessKeyId"):
      raise DuploError(
          "The AI HelpDesk returned no AWS credentials for the "
          "selected target")
    return creds

  def _resource_group_path(self,
                           resource_group: str,
                           resource_group_id: str,
                           environment: str,
                           environment_id: str) -> str:
    """Build the resource-group jitAccess route.

    The route needs the environment id as well; it is read off the
    resolved resource group record rather than asked of the caller.
    """
    rg = self.duplo.load("resource_group").find(
        name=resource_group, id=resource_group_id,
        environment=environment, environment_id=environment_id)
    rgid = self._id_of(rg)
    env_id = ((rg.get("spec") or {}).get("environmentId")
              or rg.get("environmentId"))
    if not env_id:
      raise DuploError(
          f"Resource group '{resource_group or resource_group_id}' "
          "carries no environmentId to build the jitAccess route with")
    return (f"{self._workspace_base()}/environments/{quote_plus(env_id)}"
            f"/resource-groups/{quote_plus(rgid)}/aws/jitAccess")

  def _scope_id(self, name: str) -> str:
    """Resolve a scope name to its id within the workspace.

    Without a name the workspace's only AWS scope is used; anything
    else is ambiguous and the error lists the available scope names.
    """
    scopes = self.list()
    if name:
      wanted = name.strip().lower()
      for scope in scopes:
        if str(scope.get("name", "")).strip().lower() == wanted:
          return self._id_of(scope)
      available = ", ".join(s.get("name", "?") for s in scopes) or "none"
      raise DuploError(
          f"AWS scope '{name}' not found in the workspace. "
          f"Available: {available}", 404)
    if len(scopes) == 1:
      return self._id_of(scopes[0])
    available = ", ".join(s.get("name", "?") for s in scopes) or "none"
    raise DuploError(
        f"A scope name is required when the workspace has "
        f"{len(scopes)} AWS scopes. Available: {available}", 400)
