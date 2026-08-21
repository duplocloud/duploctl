"""AI HelpDesk admin data-plane entities.

Each class below is a thin declaration over ``HelpdeskAdminResource``:
the ``collection`` string (copied verbatim from the backend, casing
included) is the only per-entity configuration, and every entity
inherits the same ``list``/``find``/``create``/``update``/``apply``/
``delete`` commands. The inventory mirrors the duploai terraform
provider's admin resources; ``hd_user`` is prefixed because ``user``
is taken by the Core Platform resource, and the workspace↔scope
mapping is exposed as ``workspace add_scope``/``remove_scope`` rather
than a resource of its own.
"""
from duplocloud.commander import Resource
from duplo_resource.helpdesk import HelpdeskAdminResource


@Resource("scope", scope="portal", client="helpdesk")
class DuploHelpdeskScope(HelpdeskAdminResource):
  """AI HelpDesk Scope

  A credentialed, filtered view over a provider's resources that can
  be attached to workspaces.
  """
  collection = "Scopes"


@Resource("provider", scope="portal", client="helpdesk")
class DuploHelpdeskProvider(HelpdeskAdminResource):
  """AI HelpDesk Provider

  A registered cloud, kubernetes, SCM, or observability provider and
  its credentials.
  """
  collection = "Providers"
  read_after_write = True


@Resource("hd_user", scope="portal", client="helpdesk")
class DuploHelpdeskUser(HelpdeskAdminResource):
  """AI HelpDesk User

  A helpdesk user account with identity, roles, and metadata. Named
  ``hd_user`` because ``user`` is the Core Platform user resource.
  """
  collection = "Users"


@Resource("persona", scope="portal", client="helpdesk")
class DuploHelpdeskPersona(HelpdeskAdminResource):
  """AI HelpDesk Persona

  An assistant profile combining a prompt with a set of skills.
  """
  collection = "Personas"


@Resource("skill", scope="portal", client="helpdesk")
class DuploHelpdeskSkill(HelpdeskAdminResource):
  """AI HelpDesk Skill

  A reusable capability defined as Markdown, a package, or a private
  git repository.
  """
  collection = "Skills"


@Resource("mcp_server", scope="portal", client="helpdesk")
class DuploHelpdeskMcpServer(HelpdeskAdminResource):
  """AI HelpDesk MCP Server

  An MCP server registration (Http, Sse, or Raw transport).
  """
  collection = "McpServers"


@Resource("permission_set", scope="portal", client="helpdesk")
class DuploHelpdeskPermissionSet(HelpdeskAdminResource):
  """AI HelpDesk Permission Set

  A named grant of workspace-scoped access.
  """
  collection = "PermissionSet"


@Resource("quota", scope="portal", client="helpdesk")
class DuploHelpdeskQuota(HelpdeskAdminResource):
  """AI HelpDesk Quota

  A spend or token limit over a daily or monthly period.
  """
  collection = "Quotas"


@Resource("quota_mapping", scope="portal", client="helpdesk")
class DuploHelpdeskQuotaMapping(HelpdeskAdminResource):
  """AI HelpDesk Quota Mapping

  Binds a quota to a platform or workspace scope and dimension.
  """
  collection = "QuotaMappings"


@Resource("command_policy", scope="portal", client="helpdesk")
class DuploHelpdeskCommandPolicy(HelpdeskAdminResource):
  """AI HelpDesk Command Policy

  Allow/block regex lists for agent-proposed commands.
  """
  collection = "CommandPolicies"


@Resource("command_policy_mapping", scope="portal", client="helpdesk")
class DuploHelpdeskCommandPolicyMapping(HelpdeskAdminResource):
  """AI HelpDesk Command Policy Mapping

  Binds a command policy to the system, a workspace, or a project.
  """
  collection = "CommandPolicyMappings"
