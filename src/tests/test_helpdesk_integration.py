import os
import random
import pytest
from duplocloud.errors import DuploError, DuploNotFound


def execute_test(func, *args, **kwargs):
    """Helper to run a resource method and fail the test on DuploError."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")


@pytest.fixture(scope="class")
def workspace_resource(duplo):
    """Load the workspace resource for the test class."""
    return duplo.load("workspace")


@pytest.mark.integration
@pytest.mark.helpdesk
@pytest.mark.usefixtures("helpdesk_ready")
class TestHelpdeskWorkspace:
    """AI HelpDesk workspace lifecycle against a live helpdesk.

    Unlike the infra/tenant suites there is no lifecycle dependency —
    the helpdesk_ready fixture gates on backend reachability instead.
    A scratch workspace is created, exercised, and deleted; the chain
    is ordered and dependency-linked so later steps skip cleanly when
    an earlier one fails.
    """

    workspace_name = f"dctl-hd-{random.randint(1000, 9999)}"
    workspace_id = None

    @pytest.mark.dependency(name="hd_workspace_list", scope="session")
    @pytest.mark.order(300)
    def test_list_workspaces(self, workspace_resource):
        """Read-only: the workspaces list responds with a list."""
        workspaces = execute_test(workspace_resource.list)
        assert isinstance(workspaces, list)

    @pytest.mark.dependency(name="hd_workspace_create",
                            depends=["hd_workspace_list"], scope="session")
    @pytest.mark.order(301)
    def test_create_workspace(self, workspace_resource):
        """Create the scratch workspace and remember its id."""
        created = execute_test(workspace_resource.create, body={
            "name": self.workspace_name,
            "description": "duploctl integration test workspace",
        })
        wid = created.get("id")
        assert wid, f"create returned no id: {created}"
        type(self).workspace_id = wid

    @pytest.mark.dependency(name="hd_workspace_find",
                            depends=["hd_workspace_create"], scope="session")
    @pytest.mark.order(302)
    def test_find_workspace(self, workspace_resource):
        """Find by name (case-insensitive) and by id return the record."""
        by_name = execute_test(workspace_resource.find,
                               self.workspace_name.upper())
        assert by_name["id"] == self.workspace_id
        by_id = execute_test(workspace_resource.find, id=self.workspace_id)
        assert by_id["name"] == self.workspace_name

    @pytest.mark.dependency(name="hd_workspace_update",
                            depends=["hd_workspace_find"], scope="session")
    @pytest.mark.order(303)
    def test_update_workspace(self, workspace_resource):
        """Full-replace update changes the description, keeps the id."""
        updated = execute_test(workspace_resource.update, body={
            "name": self.workspace_name,
            "description": "duploctl integration test workspace (updated)",
        }, id=self.workspace_id)
        assert updated.get("id") == self.workspace_id

    @pytest.mark.dependency(name="hd_workspace_apply",
                            depends=["hd_workspace_update"], scope="session")
    @pytest.mark.order(304)
    def test_apply_updates_in_place(self, workspace_resource):
        """Apply on an existing name updates rather than duplicating."""
        execute_test(workspace_resource.apply, body={
            "name": self.workspace_name,
            "description": "duploctl integration test workspace (applied)",
        })
        items = execute_test(workspace_resource.list)
        matches = [w for w in items
                   if w.get("name") == self.workspace_name]
        assert len(matches) == 1

    @pytest.mark.dependency(depends=["hd_workspace_create"], scope="session")
    @pytest.mark.order(309)
    def test_delete_workspace(self, workspace_resource):
        """Force-delete the scratch workspace and verify it is gone.

        Newer backends create workspaces delete-protected, so the
        teardown clears the protection with ``force``.
        """
        execute_test(workspace_resource.delete, id=self.workspace_id,
                     force=True)
        with pytest.raises((DuploNotFound, DuploError)):
            workspace_resource.find(self.workspace_name)


@pytest.mark.integration
@pytest.mark.helpdesk
@pytest.mark.usefixtures("helpdesk_ready")
class TestHelpdeskReadOnly:
    """Read-only smoke over helpdesk resources that exist on every install.

    Purely non-mutating: list agents and, for the first workspace found,
    list its tickets. Serves as the reachability baseline for future
    resource families.
    """

    @pytest.mark.order(310)
    def test_list_agents(self, duplo):
        agents = execute_test(duplo.load("agent").list)
        assert isinstance(agents, list)

    @pytest.mark.order(311)
    def test_list_tickets_of_first_workspace(self, duplo):
        workspaces = execute_test(duplo.load("workspace").list)
        if not workspaces:
            pytest.skip("no workspaces on this helpdesk")
        duplo.workspaceid = workspaces[0]["id"]
        tickets = execute_test(duplo.load("ticket").list)
        assert isinstance(tickets, list)


@pytest.mark.integration
@pytest.mark.helpdesk
@pytest.mark.usefixtures("helpdesk_ready")
class TestHelpdeskAgentTicket:
    """AI HelpDesk agent and ticket lifecycle against a live helpdesk.

    Two scratch agents are attached to a scratch workspace and one
    ticket is moved through reassign, status and close. The ticket is
    created without a message, so no agent is ever called. The teardown
    steps depend only on the matching create, so they still run when a
    step in between fails.
    """

    suffix = random.randint(1000, 9999)
    workspace_name = f"dctl-hd-at-{suffix}"
    agent_names = [f"dctl-hd-at-{suffix}-a", f"dctl-hd-at-{suffix}-b"]
    workspace_id = None
    agent_ids = []
    ticket_name = None

    @staticmethod
    def _agent_body(name, description="duploctl integration test agent"):
        return {
            "name": name,
            "description": description,
            "endpoint": "http://dctl-hd-agent.invalid:8000",
        }

    def _tickets(self, duplo):
        duplo.workspaceid = self.workspace_id
        return duplo.load("ticket")

    @pytest.mark.dependency(name="hd_at_workspace", scope="session")
    @pytest.mark.order(320)
    def test_create_workspace(self, duplo):
        created = execute_test(duplo.load("workspace").create, body={
            "name": self.workspace_name,
            "description": "duploctl integration test workspace",
        })
        assert created.get("id"), f"create returned no id: {created}"
        type(self).workspace_id = created["id"]

    @pytest.mark.dependency(name="hd_at_agents",
                            depends=["hd_at_workspace"], scope="session")
    @pytest.mark.order(321)
    def test_create_agents(self, duplo):
        agents = duplo.load("agent")
        ids = []
        for name in self.agent_names:
            created = execute_test(agents.create, body=self._agent_body(name))
            assert created.get("id"), f"create returned no id: {created}"
            ids.append(created["id"])
        type(self).agent_ids = ids

    @pytest.mark.dependency(depends=["hd_at_agents"], scope="session")
    @pytest.mark.order(322)
    def test_update_and_apply_agent(self, duplo):
        """Update and apply both change the record in place."""
        agents = duplo.load("agent")
        name = self.agent_names[0]
        updated = execute_test(
            agents.update, body=self._agent_body(name, "updated"))
        assert updated.get("id") == self.agent_ids[0]
        execute_test(agents.apply, body=self._agent_body(name, "applied"))
        found = execute_test(agents.find, name)
        assert found["id"] == self.agent_ids[0]
        assert found["description"] == "applied"

    @pytest.mark.dependency(name="hd_at_attached",
                            depends=["hd_at_agents"], scope="session")
    @pytest.mark.order(323)
    def test_add_agents_to_workspace(self, duplo):
        workspaces = duplo.load("workspace")
        for name in self.agent_names:
            execute_test(workspaces.add_agent,
                         id=self.workspace_id, agent_name=name)
        found = execute_test(workspaces.find, id=self.workspace_id)
        assert set(self.agent_ids) <= set(found.get("agentIds", []))

    @pytest.mark.dependency(name="hd_at_ticket",
                            depends=["hd_at_attached"], scope="session")
    @pytest.mark.order(324)
    def test_create_ticket(self, duplo):
        tickets = self._tickets(duplo)
        created = execute_test(
            tickets.create_ticket,
            title=f"{self.workspace_name} integration ticket",
            agent_id=self.agent_ids[0])
        assert created.get("ticketname"), f"no ticket name: {created}"
        type(self).ticket_name = created["ticketname"]
        names = [t.get("name") for t in execute_test(tickets.list)]
        assert self.ticket_name in names

    @pytest.mark.dependency(depends=["hd_at_ticket"], scope="session")
    @pytest.mark.order(325)
    def test_reassign_ticket(self, duplo):
        tickets = self._tickets(duplo)
        before = execute_test(tickets.assignee, self.ticket_name)
        assert before["id"] == self.agent_ids[0]
        execute_test(tickets.reassign, self.ticket_name,
                     agent_name=self.agent_names[1])
        after = execute_test(tickets.assignee, self.ticket_name)
        assert after["id"] == self.agent_ids[1]

    @pytest.mark.dependency(depends=["hd_at_ticket"], scope="session")
    @pytest.mark.order(326)
    def test_set_status_and_close_ticket(self, duplo):
        tickets = self._tickets(duplo)
        execute_test(tickets.set_status, self.ticket_name,
                     status="inProgress")
        execute_test(tickets.close, self.ticket_name)
        found = execute_test(tickets.find, self.ticket_name)
        statuses = found["history"]["statuses"]
        assert [s["status"] for s in statuses][-2:] == ["inProgress", "closed"]
        assert statuses[-1]["disposition"] == "resolved"

    @pytest.mark.dependency(depends=["hd_at_ticket"], scope="session")
    @pytest.mark.order(330)
    def test_delete_ticket(self, duplo):
        tickets = self._tickets(duplo)
        execute_test(tickets.delete, self.ticket_name)
        names = [t.get("name") for t in execute_test(tickets.list)]
        assert self.ticket_name not in names

    @pytest.mark.dependency(depends=["hd_at_attached"], scope="session")
    @pytest.mark.order(331)
    def test_remove_agents_from_workspace(self, duplo):
        workspaces = duplo.load("workspace")
        for name in self.agent_names:
            execute_test(workspaces.remove_agent,
                         id=self.workspace_id, agent_name=name)
        found = execute_test(workspaces.find, id=self.workspace_id)
        assert not set(self.agent_ids) & set(found.get("agentIds", []))

    @pytest.mark.dependency(depends=["hd_at_agents"], scope="session")
    @pytest.mark.order(332)
    def test_delete_agents(self, duplo):
        agents = duplo.load("agent")
        for agent_id in self.agent_ids:
            execute_test(agents.delete, id=agent_id)
        left = [a.get("name") for a in execute_test(agents.list)]
        assert not set(self.agent_names) & set(left)

    @pytest.mark.dependency(depends=["hd_at_workspace"], scope="session")
    @pytest.mark.order(333)
    def test_delete_workspace(self, duplo):
        workspaces = duplo.load("workspace")
        execute_test(workspaces.delete, id=self.workspace_id, force=True)
        with pytest.raises((DuploNotFound, DuploError)):
            workspaces.find(self.workspace_name)


ADMIN_RECORDS = [
    pytest.param(
        "quota",
        {"type": "Daily", "limitUsd": 1, "bufferPercentage": 10},
        {"limitUsd": 2},
        id="quota"),
    pytest.param(
        "command_policy",
        {"allowList": ["echo *"], "blockList": ["rm *"]},
        {"allowList": ["echo *", "ls *"]},
        id="command_policy"),
    pytest.param(
        "persona",
        {"description": "duploctl integration test persona", "skillIds": []},
        {"description": "duploctl integration test persona (updated)"},
        id="persona"),
]


@pytest.mark.integration
@pytest.mark.helpdesk
@pytest.mark.usefixtures("helpdesk_ready")
class TestHelpdeskAdmin:
    """AI HelpDesk admin records against a live helpdesk.

    Admin records are global to the helpdesk, so each one gets a
    run-unique name, is never attached to anything other than this
    suite's own scratch workspace, and is deleted in a ``finally`` so a
    failed step cannot leave it behind.
    """

    suffix = random.randint(1000, 9999)

    @pytest.mark.order(340)
    @pytest.mark.parametrize("kind,body,change", ADMIN_RECORDS)
    def test_admin_record_lifecycle(self, duplo, kind, body, change):
        """Create, find, update, apply in place, delete."""
        svc = duplo.load(kind)
        name = f"dctl-hd-{kind.replace('_', '-')}-{self.suffix}"
        body = {"name": name, **body}
        created = execute_test(svc.create, body=body)
        rid = created.get("id")
        assert rid, f"create returned no id: {created}"
        try:
            assert execute_test(svc.find, name.upper())["id"] == rid
            assert execute_test(svc.find, id=rid)["name"] == name

            execute_test(svc.update, body={**body, **change})
            found = execute_test(svc.find, id=rid)
            for key, value in change.items():
                assert found[key] == value

            applied = execute_test(svc.apply, body=body)
            assert applied.get("id") == rid
            matches = [r for r in execute_test(svc.list)
                       if r.get("name") == name]
            assert len(matches) == 1
        finally:
            svc.delete(id=rid)
        with pytest.raises((DuploNotFound, DuploError)):
            svc.find(id=rid)

    @pytest.mark.order(341)
    def test_command_policy_mapping_on_scratch_workspace(self, duplo):
        """A policy can be bound to a workspace and unbound again."""
        workspaces = duplo.load("workspace")
        policies = duplo.load("command_policy")
        mappings = duplo.load("command_policy_mapping")
        name = f"dctl-hd-map-{self.suffix}"
        workspace_id = policy_id = mapping_id = None
        try:
            workspace_id = execute_test(workspaces.create, body={
                "name": name,
                "description": "duploctl integration test workspace",
            })["id"]
            policy_id = execute_test(policies.create, body={
                "name": name, "allowList": ["echo *"], "blockList": [],
            })["id"]
            mapping = execute_test(mappings.create, body={
                "name": name,
                "policyId": policy_id,
                "level": "Workspace",
                "targetIds": [workspace_id],
            })
            mapping_id = mapping.get("id")
            assert mapping_id, f"create returned no id: {mapping}"
            found = execute_test(mappings.find, id=mapping_id)
            assert found["policyId"] == policy_id
            assert found["targetIds"] == [workspace_id]
        finally:
            if mapping_id:
                mappings.delete(id=mapping_id)
            if policy_id:
                policies.delete(id=policy_id)
            if workspace_id:
                workspaces.delete(id=workspace_id, force=True)
        with pytest.raises((DuploNotFound, DuploError)):
            mappings.find(id=mapping_id)


K8S_WORKSPACE_ENV = "DUPLO_HD_K8S_WORKSPACE"
K8S_NAMESPACE_ENV = "DUPLO_HD_K8S_NAMESPACE"

K8S_RECORDS = [
    pytest.param(
        "hd_configmap", "cm",
        {"data": {"greeting": "hello"}},
        {"data": {"greeting": "hello", "farewell": "bye"}},
        id="configmap"),
    pytest.param(
        "hd_secret", "secret",
        {"type": "Opaque", "stringData": {"greeting": "hello"}},
        {"type": "Opaque",
         "stringData": {"greeting": "hello", "farewell": "bye"}},
        id="secret"),
]


@pytest.fixture(scope="class")
def k8s_target(duplo, helpdesk_ready):
    """The long-lived namespace the Kubernetes records are created in.

    The workspace, environment, resource group and namespace are
    provisioned once by hand and named through the environment. The
    class skips when they are not named or the namespace is not ready.
    """
    workspace = os.getenv(K8S_WORKSPACE_ENV)
    namespace = os.getenv(K8S_NAMESPACE_ENV)
    if not (workspace and namespace):
        pytest.skip(f"{K8S_WORKSPACE_ENV} and {K8S_NAMESPACE_ENV} "
                    "are not set")
    try:
        workspace_id = duplo.load("workspace").find(workspace)["id"]
        duplo.workspaceid = workspace_id
        record = duplo.load("namespace").find(namespace)
    except DuploError as e:
        pytest.skip(f"Namespace '{namespace}' in workspace "
                    f"'{workspace}' is not available: {e}")
    if record.get("status") != "Complete":
        pytest.skip(f"Namespace '{namespace}' has status "
                    f"'{record.get('status')}'")
    spec = record["spec"]
    return {
        "workspace_id": workspace_id,
        "namespace": namespace,
        "spec": {
            "namespaceName": namespace,
            "resourceGroupId": spec["resourceGroupId"],
            "environmentId": spec["environmentId"],
            "scopeIds": spec.get("scopeIds", []),
            "mode": "Create",
            "provisioner": {"type": "Cli"},
        },
    }


@pytest.mark.integration
@pytest.mark.helpdesk
@pytest.mark.usefixtures("helpdesk_ready")
class TestHelpdeskK8s:
    """AI HelpDesk Kubernetes records against a live cluster.

    Every record is created inside one long-lived namespace that this
    suite never changes or deletes. Each record gets a run-unique name
    and is deleted in a ``finally``, which also deprovisions it from
    the cluster.
    """

    suffix = random.randint(1000, 9999)

    @pytest.fixture(autouse=True)
    def _in_namespace(self, duplo, k8s_target):
        """Select the namespace's workspace and wait on provisioning."""
        wait = duplo.wait
        duplo.workspaceid = k8s_target["workspace_id"]
        duplo.wait = True
        yield
        duplo.wait = wait

    @staticmethod
    def _body(target, name, manifest):
        return {
            "name": name,
            "spec": {
                **target["spec"],
                "k8sResource": {
                    "metadata": {"name": name,
                                 "namespace": target["namespace"]},
                    **manifest,
                },
            },
        }

    @pytest.mark.order(360)
    @pytest.mark.parametrize("kind,short,manifest,change", K8S_RECORDS)
    def test_k8s_record_lifecycle(self, duplo, k8s_target, kind, short,
                                  manifest, change):
        """Create, find, update, apply in place, delete."""
        svc = duplo.load(kind)
        name = f"dctl-hd-{short}-{self.suffix}"
        body = self._body(k8s_target, name, manifest)
        changed = self._body(k8s_target, name, change)
        created = execute_test(svc.create, body=body)
        rid = created.get("id")
        assert rid, f"create returned no id: {created}"
        try:
            found = execute_test(svc.find, name.upper())
            assert found["id"] == rid
            assert found["status"] == "Complete"
            live = execute_test(svc.find, id=rid)["result"]["k8sResource"]
            assert live["metadata"]["namespace"] == k8s_target["namespace"]
            assert set(live["data"]) == {"greeting"}

            execute_test(svc.update, body=changed)
            live = execute_test(svc.find, id=rid)["result"]["k8sResource"]
            assert set(live["data"]) == {"greeting", "farewell"}

            applied = execute_test(svc.apply, body=changed)
            assert applied.get("id") == rid
            matches = [r for r in execute_test(svc.list)
                       if r.get("name") == name]
            assert len(matches) == 1
        finally:
            svc.delete(id=rid)
        with pytest.raises((DuploNotFound, DuploError)):
            svc.find(id=rid)
