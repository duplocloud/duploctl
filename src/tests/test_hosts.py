import pytest
import time
from duplocloud.errors import DuploError, DuploStillWaiting
from .conftest import get_test_data


@pytest.fixture(scope="class")
def hosts_resource(duplo, request):
    resource = duplo.load("hosts")
    resource.duplo.wait = True
    tenant = resource.tenant["AccountName"]
    data_file = getattr(request.cls, "_data_file", "hosts-k8s")
    body = get_test_data(data_file)
    request.cls.host_name = resource.name_from_body(body)
    return resource


def execute_test(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")


# ── K8s hosts ─────────────────────────────────────────────────────────────────
# A single k8s node is the prerequisite for services, jobs, cronjobs, etc.
# Only create + find — no stop/start/reboot (that would disrupt running workloads).

@pytest.mark.integration
@pytest.mark.k8s
@pytest.mark.hosts
@pytest.mark.usefixtures("hosts_resource")
class TestHostsK8s:
    _data_file = "hosts-k8s"

    @pytest.mark.dependency(name="create_host", depends=["create_tenant"], scope="session")
    @pytest.mark.order(20)
    def test_create_host(self, hosts_resource):
        try:
            existing = hosts_resource.find(self.host_name)
            if existing:
                print(f"Host '{self.host_name}' already exists")
                return
        except DuploError:
            pass
        body = get_test_data(self._data_file)
        response = execute_test(hosts_resource.create, body)
        assert "Successfully created host" in response["message"]

    @pytest.mark.dependency(name="find_host", depends=["create_host"], scope="session")
    @pytest.mark.order(21)
    def test_find_host(self, hosts_resource):
        host = execute_test(hosts_resource.find, self.host_name)
        assert host["FriendlyName"] == self.host_name
        assert host["Status"] == "running"

    @pytest.mark.dependency(depends=["create_host"], scope="session")
    @pytest.mark.order(997)
    def test_delete_host(self, hosts_resource):
        try:
            response = hosts_resource.delete(self.host_name)
            assert "Successfully deleted host" in response["message"]
        except DuploStillWaiting:
            pass  # Delete accepted; host is still shutting down
        except DuploError as e:
            pytest.fail(f"Test failed: {e}")


# ── AWS hosts ──────────────────────────────────────────────────────────────────
# Plain EC2 instance — exercises the full node lifecycle: stop, start, reboot.
# Runs on a duplo (no-orchestrator) infra where there are no workloads to disrupt.

@pytest.mark.integration
@pytest.mark.aws
@pytest.mark.duplo
@pytest.mark.hosts
@pytest.mark.usefixtures("hosts_resource")
class TestHostsAws:
    _data_file = "hosts-aws"

    @pytest.mark.dependency(name="create_host_aws", depends=["create_tenant"], scope="session")
    @pytest.mark.order(22)
    def test_create_host(self, hosts_resource):
        try:
            existing = hosts_resource.find(self.host_name)
            if existing:
                print(f"Host '{self.host_name}' already exists")
                return
        except DuploError:
            pass
        body = get_test_data(self._data_file)
        response = execute_test(hosts_resource.create, body)
        assert "Successfully created host" in response["message"]

    @pytest.mark.dependency(name="find_host_aws", depends=["create_host_aws"], scope="session")
    @pytest.mark.order(23)
    def test_find_host(self, hosts_resource):
        host = execute_test(hosts_resource.find, self.host_name)
        assert host["FriendlyName"] == self.host_name
        assert host["Status"] == "running"

    @pytest.mark.dependency(depends=["find_host_aws"], scope="session")
    @pytest.mark.order(24)
    def test_stop_host(self, hosts_resource):
        response = execute_test(hosts_resource.stop, self.host_name)
        assert "Successfully stopped host" in response["message"]
        host = execute_test(hosts_resource.find, self.host_name)
        assert host["Status"] == "stopped"

    @pytest.mark.dependency(depends=["find_host_aws"], scope="session")
    @pytest.mark.order(25)
    def test_start_host(self, hosts_resource):
        response = execute_test(hosts_resource.start, self.host_name)
        assert "Successfully started host" in response["message"]
        host = execute_test(hosts_resource.find, self.host_name)
        assert host["Status"] == "running"

    @pytest.mark.dependency(depends=["find_host_aws"], scope="session")
    @pytest.mark.order(26)
    def test_reboot_host(self, hosts_resource):
        response = execute_test(hosts_resource.reboot, self.host_name)
        assert "Successfully rebooted host" in response["message"]
        time.sleep(60)
        host = execute_test(hosts_resource.find, self.host_name)
        assert host["Status"] == "running"

    @pytest.mark.dependency(depends=["create_host_aws"], scope="session")
    @pytest.mark.order(996)
    def test_delete_host(self, hosts_resource):
        try:
            response = hosts_resource.delete(self.host_name)
            assert "Successfully deleted host" in response["message"]
        except DuploStillWaiting:
            pass  # Delete accepted; host is still shutting down
        except DuploError as e:
            pytest.fail(f"Test failed: {e}")


# ── ECS hosts ──────────────────────────────────────────────────────────────────
# ECS container instance — prerequisite for ECS services and task definitions.
# Only create + find — no stop/start/reboot (that would disrupt running tasks).

@pytest.mark.integration
@pytest.mark.ecs
@pytest.mark.hosts
@pytest.mark.usefixtures("hosts_resource")
class TestHostsEcs:
    _data_file = "hosts-ecs"

    @pytest.mark.dependency(name="create_host", depends=["create_tenant"], scope="session")
    @pytest.mark.order(20)
    def test_create_host(self, hosts_resource):
        try:
            existing = hosts_resource.find(self.host_name)
            if existing:
                print(f"Host '{self.host_name}' already exists")
                return
        except DuploError:
            pass
        body = get_test_data(self._data_file)
        response = execute_test(hosts_resource.create, body)
        assert "Successfully created host" in response["message"]

    @pytest.mark.dependency(name="find_host", depends=["create_host"], scope="session")
    @pytest.mark.order(21)
    def test_find_host(self, hosts_resource):
        host = execute_test(hosts_resource.find, self.host_name)
        assert host["FriendlyName"] == self.host_name
        assert host["Status"] == "running"

    @pytest.mark.dependency(depends=["create_host"], scope="session")
    @pytest.mark.order(997)
    def test_delete_host(self, hosts_resource):
        try:
            response = hosts_resource.delete(self.host_name)
            assert "Successfully deleted host" in response["message"]
        except DuploStillWaiting:
            pass  # Delete accepted; host is still shutting down
        except DuploError as e:
            pytest.fail(f"Test failed: {e}")
