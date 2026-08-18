import pytest
from duplocloud.errors import (
    DuploError, DuploFailedResource, DuploNotFound, DuploStillWaiting)
from duplo_resource.helpdesk import HelpdeskAdminResource
from duplo_resource.helpdesk_admin import (
    DuploHelpdeskScope, DuploHelpdeskProvider, DuploHelpdeskUser,
    DuploHelpdeskPersona, DuploHelpdeskSkill, DuploHelpdeskMcpServer,
    DuploHelpdeskPermissionSet, DuploHelpdeskQuota,
    DuploHelpdeskQuotaMapping, DuploHelpdeskCommandPolicy,
    DuploHelpdeskCommandPolicyMapping)

_SCOPE_ID = "scope-abc-123"
_SCOPE_NAME = "aws-prod"

# (class, CLI name, backend collection) — casing copied verbatim from
# the duploai terraform provider specs.
_ADMIN_RESOURCES = [
    (DuploHelpdeskScope, "scope", "Scopes"),
    (DuploHelpdeskProvider, "provider", "Providers"),
    (DuploHelpdeskUser, "hd_user", "Users"),
    (DuploHelpdeskPersona, "persona", "Personas"),
    (DuploHelpdeskSkill, "skill", "Skills"),
    (DuploHelpdeskMcpServer, "mcp_server", "McpServers"),
    (DuploHelpdeskPermissionSet, "permission_set", "PermissionSet"),
    (DuploHelpdeskQuota, "quota", "Quotas"),
    (DuploHelpdeskQuotaMapping, "quota_mapping", "QuotaMappings"),
    (DuploHelpdeskCommandPolicy, "command_policy", "CommandPolicies"),
    (DuploHelpdeskCommandPolicyMapping, "command_policy_mapping",
     "CommandPolicyMappings"),
]


def _make_resource(mocker, cls=DuploHelpdeskScope):
    """Create an admin resource with a mocked duplo client."""
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = False
    mock_duplo.wait_timeout = None
    mock_duplo.host = "https://example.duplocloud.net"
    mock_duplo.timeout = 30
    return cls(mock_duplo)


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


_SCOPE_FULL = {"id": _SCOPE_ID, "name": _SCOPE_NAME,
               "providerId": "prov-1"}
_SCOPE_DETAIL = {"success": True, "data": _SCOPE_FULL}


@pytest.mark.unit
class TestAdminResourceRegistration:
    @pytest.mark.parametrize("cls,kind,collection", _ADMIN_RESOURCES)
    def test_kind_collection_and_base(self, mocker, cls, kind, collection):
        """Each entity declares its CLI name and verbatim collection."""
        assert cls.kind == kind
        assert cls.scope == "portal"
        assert cls._client_name == "helpdesk"
        resource = _make_resource(mocker, cls)
        assert resource._base() == f"admin/data/{collection}"


@pytest.mark.unit
class TestAdminResourceCrud:
    def test_list_walks_collection(self, mocker):
        resource = _make_resource(mocker)
        client = _make_client(mocker, resource,
                              items_responses=[[_SCOPE_FULL]])
        result = resource.list()
        assert result == [_SCOPE_FULL]
        client.get_items.assert_called_once_with("admin/data/Scopes")

    def test_find_by_name_case_insensitive(self, mocker):
        resource = _make_resource(mocker)
        client = _make_client(mocker, resource,
                              items_responses=[[_SCOPE_FULL]])
        result = resource.find(name=_SCOPE_NAME.upper())
        assert result["id"] == _SCOPE_ID
        assert "filters[name]=" in client.get_items.call_args[0][0]

    def test_find_by_id_direct(self, mocker):
        resource = _make_resource(mocker)
        client = _make_client(mocker, resource,
                              get_responses=[_SCOPE_DETAIL])
        result = resource.find(id=_SCOPE_ID)
        assert result["id"] == _SCOPE_ID
        assert client.get.call_args[0][0] == (
            f"admin/data/Scopes/{_SCOPE_ID}")

    def test_find_requires_name_or_id(self, mocker):
        resource = _make_resource(mocker)
        _make_client(mocker, resource)
        with pytest.raises(DuploError, match="name or --id"):
            resource.find()

    def test_find_missing_raises_not_found(self, mocker):
        resource = _make_resource(mocker)
        _make_client(mocker, resource, items_responses=[[]])
        with pytest.raises(DuploNotFound):
            resource.find(name="nope")

    def test_create_posts_to_collection(self, mocker):
        resource = _make_resource(mocker)
        client = _make_client(mocker, resource,
                              post_response=_SCOPE_DETAIL)
        body = {"name": _SCOPE_NAME, "providerId": "prov-1"}
        result = resource.create(body)
        assert result["id"] == _SCOPE_ID
        client.post.assert_called_once_with("admin/data/Scopes", body)

    def test_create_requires_body(self, mocker):
        resource = _make_resource(mocker)
        _make_client(mocker, resource)
        with pytest.raises(DuploError, match="request body"):
            resource.create(None)

    def test_create_read_after_write_re_reads(self, mocker):
        """Providers re-read the record because the create response
        differs from the canonical read."""
        resource = _make_resource(mocker, DuploHelpdeskProvider)
        canonical = {"success": True,
                     "data": {"id": "prov-1", "name": "aws",
                              "credentials": []}}
        client = _make_client(
            mocker, resource,
            get_responses=[canonical],
            post_response={"success": True,
                           "data": {"id": "prov-1", "name": "aws"}})
        result = resource.create({"name": "aws"})
        assert result["credentials"] == []
        assert client.get.call_args[0][0] == "admin/data/Providers/prov-1"

    def test_update_injects_id_into_body(self, mocker):
        """Admin PUTs must carry the id in the body or the backend's
        uniqueness check collides with the record itself."""
        resource = _make_resource(mocker)
        client = _make_client(mocker, resource,
                              items_responses=[[_SCOPE_FULL]],
                              put_response=_SCOPE_DETAIL)
        body = {"name": _SCOPE_NAME, "providerId": "prov-2"}
        result = resource.update(body=body)
        assert result["id"] == _SCOPE_ID
        path, payload = client.put.call_args[0]
        assert path == f"admin/data/Scopes/{_SCOPE_ID}"
        assert payload["id"] == _SCOPE_ID
        assert payload["providerId"] == "prov-2"
        # the caller's body is not mutated
        assert "id" not in body

    def test_update_with_explicit_id_skips_lookup(self, mocker):
        resource = _make_resource(mocker)
        client = _make_client(mocker, resource,
                              put_response=_SCOPE_DETAIL)
        resource.update(body={"name": _SCOPE_NAME}, id=_SCOPE_ID)
        client.get_items.assert_not_called()

    def test_apply_creates_when_missing(self, mocker):
        resource = _make_resource(mocker)
        client = _make_client(mocker, resource,
                              items_responses=[[]],
                              post_response=_SCOPE_DETAIL)
        result = resource.apply({"name": _SCOPE_NAME})
        assert result["id"] == _SCOPE_ID
        client.post.assert_called_once()
        client.put.assert_not_called()

    def test_apply_updates_when_found(self, mocker):
        resource = _make_resource(mocker)
        client = _make_client(mocker, resource,
                              items_responses=[[_SCOPE_FULL], [_SCOPE_FULL]],
                              put_response=_SCOPE_DETAIL)
        resource.apply({"name": _SCOPE_NAME})
        client.put.assert_called_once()
        client.post.assert_not_called()

    def test_delete_by_name(self, mocker):
        resource = _make_resource(mocker)
        client = _make_client(mocker, resource,
                              items_responses=[[_SCOPE_FULL]])
        result = resource.delete(name=_SCOPE_NAME)
        client.delete.assert_called_once_with(
            f"admin/data/Scopes/{_SCOPE_ID}")
        assert _SCOPE_NAME in result["message"]

    def test_cli_dispatch(self, mocker):
        """Inherited commands dispatch through resource(cmd) like the CLI."""
        resource = _make_resource(mocker)
        resource.duplo.validate = False
        _make_client(mocker, resource, items_responses=[[_SCOPE_FULL]])
        result = resource("find", _SCOPE_NAME)
        assert result["id"] == _SCOPE_ID


class _WaitingWidget(HelpdeskAdminResource):
    """Test-only resource with a fast waiter."""
    kind = "widget"
    collection = "Widgets"
    waiter = {"poll": 0.01, "timeout": 1}


@pytest.mark.unit
class TestHelpdeskWaiter:
    def _widget(self, mocker, statuses, waiter=None):
        resource = _make_resource(mocker, _WaitingWidget)
        if waiter is not None:
            resource.waiter = waiter
        responses = [{"success": True, "data": s} for s in statuses]
        _make_client(mocker, resource, get_responses=responses)
        return resource

    def test_wait_completes_on_success_state(self, mocker):
        resource = self._widget(mocker, [{"status": "Complete"}])
        resource._wait_for_ready("w-1")

    def test_wait_polls_until_complete(self, mocker):
        resource = self._widget(
            mocker, [{"status": "Provisioning"}, {"status": "Complete"}])
        resource._wait_for_ready("w-1")
        assert resource.client.get.call_count == 2

    def test_wait_failure_state_aborts_with_detail(self, mocker):
        resource = self._widget(
            mocker, [{"status": "Failed", "blockedReason": "quota hit"}])
        with pytest.raises(DuploFailedResource, match="quota hit"):
            resource._wait_for_ready("w-1")

    def test_wait_waiting_for_approval_aborts(self, mocker):
        resource = self._widget(
            mocker, [{"status": "WaitingForApproval"}])
        with pytest.raises(DuploFailedResource, match="manual approval"):
            resource._wait_for_ready("w-1")

    def test_wait_ready_gate_blocks_until_ready(self, mocker):
        waiter = {"poll": 0.01, "timeout": 1,
                  "ready_path": "result.liveState",
                  "ready_state": "running"}
        resource = self._widget(
            mocker,
            [{"status": "Complete", "result": {"liveState": "pending"}},
             {"status": "Complete", "result": {"liveState": "running"}}],
            waiter=waiter)
        resource._wait_for_ready("w-1")
        assert resource.client.get.call_count == 2

    def test_wait_times_out(self, mocker):
        resource = self._widget(
            mocker, [{"status": "Provisioning"}] * 10,
            waiter={"poll": 0.01, "timeout": 0.02})
        with pytest.raises(DuploStillWaiting, match="Timed out"):
            resource._wait_for_ready("w-1")

    def test_create_waits_when_global_wait_set(self, mocker):
        resource = self._widget(mocker, [])
        resource.duplo.wait = True
        resource.client.post.return_value.json.return_value = {
            "success": True, "data": {"id": "w-1"}}
        waited = mocker.patch.object(resource, "_wait_for_ready")
        resource.create({"name": "w"})
        waited.assert_called_once_with("w-1")

    def test_create_does_not_wait_without_waiter(self, mocker):
        resource = _make_resource(mocker)
        resource.duplo.wait = True
        _make_client(mocker, resource,
                     post_response=_SCOPE_DETAIL)
        waited = mocker.patch.object(resource, "_wait_for_ready")
        resource.create({"name": _SCOPE_NAME})
        waited.assert_not_called()


@pytest.mark.unit
class TestWorkspaceScopeMapping:
    def _workspace(self, mocker):
        from duplo_resource.workspace import DuploWorkspace
        mock_duplo = mocker.MagicMock()
        mock_duplo.wait = False
        mock_duplo.host = "https://example.duplocloud.net"
        mock_duplo.timeout = 30
        ws = DuploWorkspace(mock_duplo)
        mocker.patch.object(ws, "find",
                            return_value={"id": "ws-1", "name": "platform"})
        mocker.patch.object(ws, "client", mocker.MagicMock())
        scope_svc = mocker.MagicMock()
        scope_svc.find.return_value = {"id": _SCOPE_ID,
                                       "name": _SCOPE_NAME}
        mock_duplo.load.return_value = scope_svc
        return ws, scope_svc

    def test_add_scope(self, mocker):
        ws, scope_svc = self._workspace(mocker)
        result = ws.add_scope(name="platform", scope_name=_SCOPE_NAME)
        ws.client.post.assert_called_once_with(
            f"admin/data/workspaces/ws-1/scopes/{_SCOPE_ID}")
        scope_svc.find.assert_called_once_with(name=_SCOPE_NAME, id=None)
        assert _SCOPE_NAME in result["message"]

    def test_remove_scope(self, mocker):
        ws, _ = self._workspace(mocker)
        ws.remove_scope(name="platform", scope_id=_SCOPE_ID)
        ws.client.delete.assert_called_once_with(
            f"admin/data/workspaces/ws-1/scopes/{_SCOPE_ID}")
