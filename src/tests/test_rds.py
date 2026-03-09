import pytest
import time
from duplocloud.errors import DuploError, DuploStillWaiting
from .conftest import get_test_data


@pytest.fixture(scope="class")
def rds_resource(duplo, request):
    resource = duplo.load("rds")
    resource.duplo.wait = True
    request.cls.primary_name = f"duplo{get_test_data('rds')['Identifier']}"
    request.cls.replica_name = f"duplo{get_test_data('rds-read')['Identifier']}"
    return resource


def execute_test(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except (DuploError, DuploStillWaiting) as e:
        pytest.fail(f"Test failed: {e}")


@pytest.mark.integration
@pytest.mark.aws
@pytest.mark.rds
@pytest.mark.usefixtures("rds_resource")
class TestRDS:

    # ── engine version validation ──────────────────────────────────────────

    @pytest.mark.dependency(name="rds_engine_version", depends=["create_tenant"], scope="session")
    @pytest.mark.order(40)
    def test_engine_version_available(self, rds_resource):
        """Verify the engine version in rds.yaml is available in this environment.

        Skips all downstream RDS tests with a clear message if the version is absent
        from what DuploCloud reports for this region.
        """
        r = rds_resource
        body = get_test_data("rds")
        engine_int = body.get("Engine", 0)
        requested_version = body.get("EngineVersion")
        engine_names = {0: "mysql", 1: "postgres", 2: "aurora-mysql", 3: "aurora-postgresql", 6: "mariadb"}
        engine_name = engine_names.get(engine_int, str(engine_int))

        versions_response = execute_test(r.engine_versions)
        available = [
            v.get("V")
            for v in versions_response.get("EngineVersions", {}).get("Data", {}).get(engine_name, [])
        ]
        if available and requested_version not in available:
            pytest.skip(
                f"RDS engine version '{requested_version}' is not available for '{engine_name}' "
                f"in this environment. Available versions: {available}"
            )

    # ── primary lifecycle ──────────────────────────────────────────────────

    @pytest.mark.dependency(name="create_rds", depends=["rds_engine_version"], scope="session")
    @pytest.mark.order(41)
    def test_create_rds(self, rds_resource):
        r = rds_resource
        body = get_test_data("rds")
        try:
            existing = r.find(self.primary_name)
            if existing and existing.get("InstanceStatus") == "available":
                print(f"RDS '{self.primary_name}' already exists and is available")
                return
        except DuploError:
            pass
        # Retry loop: a prior instance may still be deleting (409 "already used").
        start_time = time.time()
        while True:
            try:
                response = r.create(body=body)
                assert response is not None
                break
            except DuploError as e:
                elapsed = time.time() - start_time
                if elapsed > r.wait_timeout:
                    pytest.fail(f"Failed to create RDS after {int(elapsed)}s: {e}")
                print(f"Create attempt failed: {e}. Retrying in 10 seconds...")
                time.sleep(10)

    @pytest.mark.dependency(name="find_rds", depends=["create_rds"], scope="session")
    @pytest.mark.order(42)
    def test_find_rds(self, rds_resource):
        r = rds_resource
        db = execute_test(r.find, self.primary_name)
        assert db["Identifier"] == self.primary_name
        assert db["InstanceStatus"] == "available"

    @pytest.mark.dependency(depends=["find_rds"], scope="session")
    @pytest.mark.order(43)
    def test_resize_rds(self, rds_resource):
        r = rds_resource
        response = execute_test(r.set_instance_size, self.primary_name, "db.t3.medium")
        assert "resized" in response["message"]

    # ── stop / start (must run before replica exists — AWS rejects stop on replica source) ──

    @pytest.mark.dependency(depends=["find_rds"], scope="session")
    @pytest.mark.order(44)
    def test_stop_rds(self, rds_resource):
        r = rds_resource
        response = execute_test(r.stop, self.primary_name)
        assert "stopped" in response["message"]

    @pytest.mark.dependency(name="start_rds", depends=["find_rds"], scope="session")
    @pytest.mark.order(45)
    def test_start_rds(self, rds_resource):
        r = rds_resource
        response = execute_test(r.start, self.primary_name)
        assert "started" in response["message"]

    # ── read replica ───────────────────────────────────────────────────────

    @pytest.mark.dependency(name="create_rds_replica", depends=["start_rds"], scope="session")
    @pytest.mark.order(46)
    def test_create_rds_replica(self, rds_resource):
        r = rds_resource
        body = get_test_data("rds-read")
        try:
            existing = r.find(self.replica_name)
            if existing and existing.get("InstanceStatus") == "available":
                print(f"RDS replica '{self.replica_name}' already exists and is available")
                return
        except DuploError:
            pass
        start_time = time.time()
        while True:
            try:
                response = r.create(body=body)
                assert response is not None
                break
            except DuploError as e:
                elapsed = time.time() - start_time
                if elapsed > r.wait_timeout:
                    pytest.fail(f"Failed to create RDS replica after {int(elapsed)}s: {e}")
                print(f"Create attempt failed: {e}. Retrying in 10 seconds...")
                time.sleep(10)

    @pytest.mark.dependency(name="find_rds_replica", depends=["create_rds_replica"], scope="session")
    @pytest.mark.order(47)
    def test_find_rds_replica(self, rds_resource):
        r = rds_resource
        db = execute_test(r.find, self.replica_name)
        assert db["Identifier"] == self.replica_name
        assert db["InstanceStatus"] == "available"

    # ── teardown ───────────────────────────────────────────────────────────

    @pytest.mark.dependency(depends=["create_rds_replica"], scope="session")
    @pytest.mark.order(994)
    def test_delete_rds_replica(self, rds_resource):
        r = rds_resource
        try:
            r.delete(self.replica_name)
        except DuploError as e:
            if e.code == 404:
                print(f"RDS replica '{self.replica_name}' already deleted")
            else:
                pytest.fail(f"Failed to delete RDS replica: {e}")

    @pytest.mark.dependency(depends=["create_rds"], scope="session")
    @pytest.mark.order(995)
    def test_delete_rds(self, rds_resource):
        r = rds_resource
        try:
            r.delete(self.primary_name)
        except DuploError as e:
            if e.code == 404:
                print(f"RDS '{self.primary_name}' already deleted")
            else:
                pytest.fail(f"Failed to delete RDS: {e}")
