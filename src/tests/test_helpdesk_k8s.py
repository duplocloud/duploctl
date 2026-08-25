import pytest
from duplocloud.errors import (
    DuploError, DuploFailedResource, DuploNotFound, DuploStillWaiting)
from duplo_resource.helpdesk import HelpdeskWorkspaceResource
from duplo_resource.helpdesk_k8s import (
    DuploHelpdeskConfigMap, DuploHelpdeskSecret, DuploHelpdeskCronJob,
    DuploHelpdeskJob, DuploHelpdeskIngress, DuploHelpdeskPvc,
    DuploHelpdeskResourceQuota, DuploHelpdeskStorageClass,
    DuploHelpdeskNamespace, DuploHelmRelease, DuploHelmRepository,
    DuploK8sCredentials)

_WID = "ws-1"
_RID = "cm-abc-123"
_NAME = "app-config"

# (class, CLI name, backend collection, immutable) — collections and
# request constants copied verbatim from the duploai terraform
# provider specs.
_K8S_RESOURCES = [
    (DuploHelpdeskConfigMap, "hd_configmap", "K8sConfigMaps", False),
    (DuploHelpdeskSecret, "hd_secret", "K8sSecrets", False),
    (DuploHelpdeskCronJob, "hd_cronjob", "K8sCronJobs", False),
    (DuploHelpdeskJob, "hd_job", "K8sJobs", True),
    (DuploHelpdeskIngress, "hd_ingress", "K8sIngresses", False),
    (DuploHelpdeskPvc, "hd_pvc", "K8sPersistentVolumeClaims", False),
    (DuploHelpdeskResourceQuota, "resource_quota",
     "K8sResourceQuotas", False),
    (DuploHelpdeskStorageClass, "hd_storageclass",
     "K8sStorageClasses", False),
    (DuploHelpdeskNamespace, "namespace", "Namespaces", True),
    (DuploHelmRelease, "helm_release", "K8sHelmReleases", False),
    (DuploHelmRepository, "helm_repository", "K8sHelmRepositories", False),
]


def _make_resource(mocker, cls=DuploHelpdeskConfigMap):
    """Create a K8s resource with a mocked duplo client and workspace."""
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = False
    mock_duplo.wait_timeout = None
    mock_duplo.host = "https://example.duplocloud.net"
    mock_duplo.timeout = 30
    resource = cls(mock_duplo)
    mocker.patch.object(type(resource), "workspace_id",
                        mocker.PropertyMock(return_value=_WID),
                        create=True)
    return resource


def _make_client(mocker, resource, get_responses=(), items_responses=None,
                 post_response=None, put_response=None):
    """Wire a mock client returning the supplied JSON payloads in order."""
    mock_client = mocker.MagicMock()
    get_mocks = [mocker.MagicMock() for _ in get_responses]
    for m, payload in zip(get_mocks, get_responses):
        m.json.return_value = payload
    mock_client.get.side_effect = get_mocks
    if items_responses is not None:
        mock_client.get_items.side_effect = items_responses
    if post_response is not None:
        mock_client.post.return_value.json.return_value = post_response
    if put_response is not None:
        mock_client.put.return_value.json.return_value = put_response
    mocker.patch.object(resource, "client", mock_client, create=True)
    return mock_client


_FULL = {"id": _RID, "name": _NAME, "status": "Complete"}
_DETAIL = {"success": True, "data": _FULL}


@pytest.mark.unit
class TestK8sResourceRegistration:
    @pytest.mark.parametrize("cls,kind,collection,immutable", _K8S_RESOURCES)
    def test_kind_collection_and_base(self, mocker, cls, kind, collection,
                                      immutable):
        """Each entity declares its CLI name, collection, and flags."""
        assert cls.kind == kind
        assert cls.scope == "workspace"
        assert cls._client_name == "helpdesk"
        assert cls.immutable is immutable
        assert cls.deprovision is True
        assert cls.waiter is not None
        resource = _make_resource(mocker, cls)
        assert resource._base() == (
            f"user/data/workspaces/{_WID}/environment/{collection}")

    def test_request_constants_match_specs(self):
        """Spot-check the provider spec constants survived transcription."""
        assert DuploHelpdeskConfigMap.request_constants == {
            "spec.k8sResource.apiVersion": "v1",
            "spec.k8sResource.kind": "ConfigMap"}
        assert DuploHelpdeskJob.request_constants == {"spec.mode": "Create"}
        assert DuploHelpdeskIngress.request_constants[
            "spec.k8sResource.apiVersion"] == "networking.k8s.io/v1"
        assert DuploHelpdeskStorageClass.request_constants[
            "spec.k8sResource.apiVersion"] == "storage.k8s.io/v1"
        assert DuploHelmRelease.request_constants == {
            "spec.k8sResource.kind": "HelmRelease"}
        assert DuploHelpdeskNamespace.request_constants == {}


@pytest.mark.unit
class TestK8sCrud:
    def test_create_injects_constants(self, mocker):
        resource = _make_resource(mocker)
        client = _make_client(mocker, resource, post_response=_DETAIL)
        body = {"name": _NAME, "spec": {"environmentId": "env-1"}}
        resource.create(body)
        _, payload = client.post.call_args[0]
        assert payload["spec"]["k8sResource"]["apiVersion"] == "v1"
        assert payload["spec"]["k8sResource"]["kind"] == "ConfigMap"
        assert payload["spec"]["environmentId"] == "env-1"
        # the caller's body is never mutated
        assert "k8sResource" not in body["spec"]

    def test_create_constants_never_clobber(self, mocker):
        resource = _make_resource(mocker, DuploHelpdeskCronJob)
        client = _make_client(mocker, resource, post_response=_DETAIL)
        resource.create({"name": _NAME, "spec": {"mode": "Adopt"}})
        _, payload = client.post.call_args[0]
        assert payload["spec"]["mode"] == "Adopt"

    def test_update_injects_id_and_constants(self, mocker):
        resource = _make_resource(mocker)
        client = _make_client(mocker, resource,
                              items_responses=[[_FULL]],
                              put_response=_DETAIL)
        body = {"name": _NAME}
        resource.update(body=body)
        path, payload = client.put.call_args[0]
        assert path.endswith(f"/K8sConfigMaps/{_RID}")
        assert payload["id"] == _RID
        assert payload["spec"]["k8sResource"]["kind"] == "ConfigMap"
        assert "id" not in body

    @pytest.mark.parametrize("cls", [DuploHelpdeskJob,
                                     DuploHelpdeskNamespace])
    def test_immutable_update_rejected(self, mocker, cls):
        resource = _make_resource(mocker, cls)
        client = _make_client(mocker, resource)
        with pytest.raises(DuploError, match="immutable"):
            resource.update(body={"name": _NAME})
        client.put.assert_not_called()

    def test_immutable_apply_over_existing_rejected(self, mocker):
        resource = _make_resource(mocker, DuploHelpdeskNamespace)
        client = _make_client(mocker, resource, items_responses=[[_FULL]])
        with pytest.raises(DuploError, match="immutable"):
            resource.apply({"name": _NAME})
        client.post.assert_not_called()

    def test_immutable_apply_creates_when_missing(self, mocker):
        resource = _make_resource(mocker, DuploHelpdeskNamespace)
        client = _make_client(mocker, resource, items_responses=[[]],
                              post_response=_DETAIL)
        result = resource.apply({"name": _NAME})
        assert result["id"] == _RID
        client.post.assert_called_once()

    def test_find_by_name_and_id(self, mocker):
        resource = _make_resource(mocker)
        client = _make_client(mocker, resource, items_responses=[[_FULL]])
        assert resource.find(name=_NAME.upper())["id"] == _RID
        assert "filters[name]=" in client.get_items.call_args[0][0]

    def test_create_waits_when_global_wait_set(self, mocker):
        resource = _make_resource(mocker)
        resource.duplo.wait = True
        _make_client(mocker, resource, post_response=_DETAIL)
        waited = mocker.patch.object(resource, "_wait_for_ready")
        resource.create({"name": _NAME})
        waited.assert_called_once_with(_RID)


@pytest.mark.unit
class TestK8sDelete:
    def _responses(self, statuses):
        return [{"success": True,
                 "data": {"id": _RID, "status": s}} for s in statuses]

    def test_delete_deprovisions_then_deletes(self, mocker):
        resource = _make_resource(mocker)
        resource.waiter = {"poll": 0.01, "timeout": 1}
        client = _make_client(
            mocker, resource,
            get_responses=self._responses(["DeProvisioning",
                                           "DeProvisioned"]),
            items_responses=[[_FULL]])
        result = resource.delete(name=_NAME)
        client.post.assert_called_once()
        assert client.post.call_args[0][0].endswith(
            f"/K8sConfigMaps/{_RID}/deprovision")
        client.delete.assert_called_once()
        assert client.delete.call_args[0][0].endswith(
            f"/K8sConfigMaps/{_RID}")
        assert _NAME in result["message"]

    def test_delete_tolerates_deprovision_404(self, mocker):
        """A record with no cloud infra left 404s the deprovision —
        the delete still proceeds."""
        resource = _make_resource(mocker)
        resource.waiter = {"poll": 0.01, "timeout": 1}
        client = _make_client(
            mocker, resource,
            get_responses=self._responses(["DeProvisioned"]),
            items_responses=[[_FULL]])
        client.post.side_effect = DuploNotFound(_RID, "hd_configmap")
        resource.delete(name=_NAME)
        client.delete.assert_called_once()

    def test_deprovision_wait_aborts_on_failure(self, mocker):
        resource = _make_resource(mocker)
        resource.waiter = {"poll": 0.01, "timeout": 1}
        responses = [{"success": True,
                      "data": {"id": _RID, "status": "DeprovisionFailed",
                               "blockedReason": "volume in use"}}]
        client = _make_client(mocker, resource, get_responses=responses,
                              items_responses=[[_FULL]])
        with pytest.raises(DuploFailedResource, match="volume in use"):
            resource.delete(name=_NAME)
        client.delete.assert_not_called()

    def test_deprovision_wait_treats_gone_as_done(self, mocker):
        resource = _make_resource(mocker)
        resource.waiter = {"poll": 0.01, "timeout": 1}
        client = _make_client(mocker, resource, items_responses=[[_FULL]])
        client.get.side_effect = DuploNotFound(_RID, "hd_configmap")
        client.delete.side_effect = DuploNotFound(_RID, "hd_configmap")
        result = resource.delete(name=_NAME)
        assert "deleted" in result["message"]

    def test_delete_with_wait_confirms_gone(self, mocker):
        """With --wait, delete polls after the DELETE until 404."""
        resource = _make_resource(mocker)
        resource.duplo.wait = True
        resource.waiter = {"poll": 0.01, "timeout": 1}
        client = _make_client(mocker, resource, items_responses=[[_FULL]])
        deprovisioned = mocker.MagicMock()
        deprovisioned.json.return_value = self._responses(
            ["DeProvisioned"])[0]
        # deprovision-wait sees DeProvisioned, gone-wait sees 404
        client.get.side_effect = [deprovisioned,
                                  DuploNotFound(_RID, "hd_configmap")]
        resource.delete(name=_NAME)
        client.delete.assert_called_once()
        assert client.get.call_count == 2


@pytest.mark.unit
class TestHelmReleaseWaiter:
    def _release(self, mocker, records):
        resource = _make_resource(mocker, DuploHelmRelease)
        resource.waiter = {**DuploHelmRelease.waiter,
                           "poll": 0.01, "timeout": 1}
        responses = [{"success": True, "data": r} for r in records]
        _make_client(mocker, resource, get_responses=responses)
        return resource

    def _record(self, ready=None, stalled=None, message=None):
        conditions = []
        if ready is not None:
            c = {"type": "Ready", "status": ready}
            if message:
                c["message"] = message
            conditions.append(c)
        if stalled is not None:
            conditions.append({"type": "Stalled", "status": stalled})
        return {"id": "hr-1", "status": "Complete",
                "result": {"k8sResource": {"status":
                                           {"conditions": conditions}}}}

    def test_ready_condition_gates_success(self, mocker):
        resource = self._release(mocker, [
            self._record(ready="False"),
            self._record(ready="True"),
        ])
        resource._wait_for_ready("hr-1")
        assert resource.client.get.call_count == 2

    def test_stalled_condition_is_terminal(self, mocker):
        resource = self._release(mocker, [
            self._record(ready="False", stalled="True",
                         message="chart not found"),
        ])
        with pytest.raises(DuploFailedResource,
                           match="not retrying further: chart not found"):
            resource._wait_for_ready("hr-1")

    def test_condition_selector_parsing(self, mocker):
        resource = _make_resource(mocker, DuploHelmRelease)
        record = self._record(ready="True")
        path = "result.k8sResource.status.conditions[type=Ready].status"
        assert resource._extract_path(record, path) == "True"
        assert resource._extract_path(
            record, "result.k8sResource.status.conditions[type=Nope].status"
        ) is None


@pytest.mark.unit
class TestK8sCredentials:
    def test_find_by_id_hits_jit_access(self, mocker):
        resource = _make_resource(mocker, DuploK8sCredentials)
        creds = {"success": True,
                 "data": {"apiServer": "https://eks.example",
                          "token": "k8s-jit-token",
                          "certificateAuthorityDataBase64": "Y2E=",
                          "defaultNamespace": "duplo-ai"}}
        client = _make_client(mocker, resource, get_responses=[creds])
        result = resource.find(id="cluster-1")
        assert result["token"] == "k8s-jit-token"
        assert client.get.call_args[0][0].endswith(
            "/environment/Clusters/cluster-1/jitAccess")

    def test_find_by_name_resolves_cluster_first(self, mocker):
        resource = _make_resource(mocker, DuploK8sCredentials)
        creds = {"success": True, "data": {"apiServer": "x", "token": "t"}}
        client = _make_client(
            mocker, resource,
            get_responses=[creds],
            items_responses=[[{"id": "cluster-1", "name": "prod-eks"}]])
        result = resource.find(name="PROD-EKS")
        assert result["token"] == "t"
        assert client.get.call_args[0][0].endswith(
            "/Clusters/cluster-1/jitAccess")

    def test_no_mutating_commands(self):
        from duplocloud.commander import commands_for
        cmds = commands_for("k8s_credentials")
        for verb in ("create", "update", "delete", "apply"):
            assert verb not in cmds
