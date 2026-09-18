"""AI HelpDesk Kubernetes resource family.

Workspace-scoped entities on the user data plane
(``user/data/workspaces/{workspace_id}/environment/<Collection>``),
one thin subclass of ``HelpdeskWorkspaceResource`` per backend
collection. Collection names, request constants, immutability, and
waiter overrides are copied verbatim from the duploai terraform
provider specs. CLI names take an ``hd_`` prefix only where the Core
Platform already owns the plain name (configmap, secret, cronjob, job,
ingress, pvc, storageclass), matching the ``hd_lambda``/``hd_user``
precedent.
"""
from urllib.parse import quote_plus

from duplocloud.commander import Command, Resource
from duplocloud.errors import DuploError
from duplo_resource.helpdesk import (
    HelpdeskResource, HelpdeskWorkspaceResource)
from duplo_resource.helpdesk_client import unwrap_data
import duplocloud.args as args


@Resource("hd_configmap", scope="workspace", client="helpdesk")
class DuploHelpdeskConfigMap(HelpdeskWorkspaceResource):
  """Manage AI HelpDesk Kubernetes ConfigMaps."""
  collection = "K8sConfigMaps"
  request_constants = {
    "spec.k8sResource.apiVersion": "v1",
    "spec.k8sResource.kind": "ConfigMap",
  }


@Resource("hd_secret", scope="workspace", client="helpdesk")
class DuploHelpdeskSecret(HelpdeskWorkspaceResource):
  """Manage AI HelpDesk Kubernetes Secrets."""
  collection = "K8sSecrets"
  request_constants = {
    "spec.k8sResource.apiVersion": "v1",
    "spec.k8sResource.kind": "Secret",
  }


@Resource("hd_cronjob", scope="workspace", client="helpdesk")
class DuploHelpdeskCronJob(HelpdeskWorkspaceResource):
  """Manage AI HelpDesk Kubernetes CronJobs."""
  collection = "K8sCronJobs"
  request_constants = {"spec.mode": "Create"}


@Resource("hd_job", scope="workspace", client="helpdesk")
class DuploHelpdeskJob(HelpdeskWorkspaceResource):
  """Manage AI HelpDesk Kubernetes Jobs.

  Jobs are immutable: to change one, delete and recreate it.
  """
  collection = "K8sJobs"
  request_constants = {"spec.mode": "Create"}
  immutable = True


@Resource("hd_ingress", scope="workspace", client="helpdesk")
class DuploHelpdeskIngress(HelpdeskWorkspaceResource):
  """Manage AI HelpDesk Kubernetes Ingresses."""
  collection = "K8sIngresses"
  request_constants = {
    "spec.mode": "Create",
    "spec.k8sResource.apiVersion": "networking.k8s.io/v1",
    "spec.k8sResource.kind": "Ingress",
  }


@Resource("hd_pvc", scope="workspace", client="helpdesk")
class DuploHelpdeskPvc(HelpdeskWorkspaceResource):
  """Manage AI HelpDesk Kubernetes PersistentVolumeClaims."""
  collection = "K8sPersistentVolumeClaims"
  request_constants = {
    "spec.k8sResource.apiVersion": "v1",
    "spec.k8sResource.kind": "PersistentVolumeClaim",
  }


@Resource("resource_quota", scope="workspace", client="helpdesk")
class DuploHelpdeskResourceQuota(HelpdeskWorkspaceResource):
  """Manage AI HelpDesk Kubernetes ResourceQuotas."""
  collection = "K8sResourceQuotas"
  request_constants = {
    "spec.k8sResource.apiVersion": "v1",
    "spec.k8sResource.kind": "ResourceQuota",
  }


@Resource("hd_storageclass", scope="workspace", client="helpdesk")
class DuploHelpdeskStorageClass(HelpdeskWorkspaceResource):
  """Manage AI HelpDesk Kubernetes StorageClasses."""
  collection = "K8sStorageClasses"
  request_constants = {
    "spec.k8sResource.apiVersion": "storage.k8s.io/v1",
    "spec.k8sResource.kind": "StorageClass",
  }


@Resource("namespace", scope="workspace", client="helpdesk")
class DuploHelpdeskNamespace(HelpdeskWorkspaceResource):
  """Manage AI HelpDesk Kubernetes Namespaces.

  Namespaces are immutable: to change one, delete and recreate it.
  """
  collection = "Namespaces"
  immutable = True


@Resource("helm_release", scope="workspace", client="helpdesk")
class DuploHelmRelease(HelpdeskWorkspaceResource):
  """Manage AI HelpDesk Helm releases.

  A release's ``--wait`` readiness goes beyond the provisioning
  status: Flux must also report the release's ``Ready`` condition as
  ``True``, and a ``Stalled`` condition is a terminal failure.
  """
  collection = "K8sHelmReleases"
  request_constants = {"spec.k8sResource.kind": "HelmRelease"}
  waiter = {
    "poll": 15,
    "timeout": 1200,
    "ready_path": "result.k8sResource.status.conditions[type=Ready].status",
    "ready_state": "True",
    "ready_failure_path":
        "result.k8sResource.status.conditions[type=Stalled].status",
    "ready_failure_states": {
      "True": ("Helm release failed to reconcile and Flux is not "
               "retrying further"),
    },
    "failure_detail_path":
        "result.k8sResource.status.conditions[type=Ready].message",
  }


@Resource("helm_repository", scope="workspace", client="helpdesk")
class DuploHelmRepository(HelpdeskWorkspaceResource):
  """Manage AI HelpDesk Helm repositories."""
  collection = "K8sHelmRepositories"
  request_constants = {"spec.k8sResource.kind": "HelmRepository"}


@Resource("k8s_credentials", scope="workspace", client="helpdesk")
class DuploK8sCredentials(HelpdeskResource):
  """Fetch just-in-time Kubernetes credentials for a helpdesk cluster.

  Read-only: returns the API server endpoint, a short-lived bearer
  token, and the cluster certificate authority for any cluster the
  platform provisions (EKS, AKS, or registered K8S_ONLY clusters).
  """

  def _base(self) -> str:
    """Build the workspace-scoped Clusters endpoint."""
    return (f"user/data/workspaces/{quote_plus(self.workspace_id)}/"
            "environment/Clusters")

  @Command("ls")
  def list(self) -> list:
    """List the clusters in the workspace.

    Usage: CLI Usage
      ```sh
      duploctl k8s_credentials list
      ```

    Returns:
      resources: The workspace's clusters.
    """
    return self.client.get_items(self._base())

  @Command()
  def find(self,
           name: args.NAME = None,
           id: args.ID = None) -> dict:
    """Fetch JIT credentials for a cluster by name or id.

    Mints a short-lived bearer token per call.

    Usage: CLI Usage
      ```sh
      duploctl k8s_credentials find <cluster name>
      duploctl k8s_credentials find --id <cluster id>
      ```

    Args:
      name: The cluster name.
      id: The cluster id. Skips the name lookup when provided.

    Returns:
      credentials: The API server endpoint, bearer token, certificate
        authority data, and default namespace.

    Raises:
      DuploError: If neither name nor id is given.
      DuploNotFound: If no cluster matches.
    """
    cid = id or self._id_of(self._find_in_workspace(name, None))
    response = self.client.get(
        f"{self._base()}/{quote_plus(cid)}/jitAccess").json()
    creds = unwrap_data(response)
    if not creds or not isinstance(creds, dict):
      raise DuploError(
          f"The AI HelpDesk returned no credentials for cluster "
          f"'{name or cid}'")
    return creds
