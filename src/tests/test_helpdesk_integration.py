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
        """Delete the scratch workspace and verify it is gone."""
        execute_test(workspace_resource.delete, id=self.workspace_id)
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
