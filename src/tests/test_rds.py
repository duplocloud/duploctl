import pytest
import time
from unittest.mock import MagicMock
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


# ---------------------------------------------------------------------------
# Unit tests — stop/start engine routing & cluster dedup
# ---------------------------------------------------------------------------

def _make_rds(mocker):
    """Return a DuploRDS with a mocked HTTP client and tenant id.

    The ``@Resource(scope="tenant")`` decorator sets ``self.client`` and
    lazy tenant properties in the wrapped ``__init__``. We replace the
    client with a MagicMock and pin ``_tenant_id`` so ``endpoint()`` and
    cluster paths resolve without any API calls.
    """
    from duplo_resource.rds import DuploRDS
    duplo = MagicMock()
    duplo.wait = False
    resource = DuploRDS(duplo)
    resource.client = MagicMock()
    resource._tenant_id = "tid-1"
    return resource


@pytest.mark.unit
@pytest.mark.rds
@pytest.mark.parametrize("engine,expected", [
    (0, "instance"),    # MySql
    (1, "instance"),    # PostgreSql
    (8, "cluster"),     # AuroraMySql
    (9, "cluster"),     # AuroraPostgreSql
    (16, "cluster"),    # Aurora (legacy)
    (11, "skip"),       # Serverless v1 MySql
    (12, "skip"),       # Serverless v1 PostgreSql
    (13, "skip"),       # DocumentDB (skip until validated)
    ("PostgreSql", "instance"),
    ("AuroraPostgreSql", "cluster"),
    ("AuroraServerlessMySql", "skip"),
])
def test_engine_category(mocker, engine, expected):
    """_engine_category classifies int and string engines correctly."""
    r = _make_rds(mocker)
    assert r._engine_category({"Engine": engine}) == expected


@pytest.mark.unit
@pytest.mark.rds
def test_stop_routes_instance_engine_to_instance_endpoint(mocker):
    """A regular RDS instance stops via the instance endpoint."""
    r = _make_rds(mocker)
    mocker.patch.object(r, "find", return_value={
        "Identifier": "db1", "Engine": 1, "InstanceStatus": "available"
    })
    r.stop("duplodb1")
    r.client.post.assert_called_once_with(
        "v3/subscriptions/tid-1/aws/rds/instance/duplodb1/stop"
    )


@pytest.mark.unit
@pytest.mark.rds
def test_stop_routes_cluster_engine_to_cluster_endpoint(mocker):
    """An Aurora instance stops via the cluster endpoint with ClusterIdentifier."""
    r = _make_rds(mocker)
    mocker.patch.object(r, "find", return_value={
        "Identifier": "db1", "Engine": 9, "ClusterIdentifier": "duploclus1"
    })
    r.stop("duplodb1")
    r.client.post.assert_called_once_with(
        "v3/subscriptions/tid-1/aws/rds/cluster/duploclus1/stop"
    )


@pytest.mark.unit
@pytest.mark.rds
def test_stop_skips_serverless_v1(mocker):
    """Serverless v1 is skipped — no endpoint is called."""
    r = _make_rds(mocker)
    mocker.patch.object(r, "find", return_value={
        "Identifier": "db1", "Engine": 11
    })
    result = r.stop("duplodb1")
    r.client.post.assert_not_called()
    assert "skipped" in result["message"]


@pytest.mark.unit
@pytest.mark.rds
def test_stop_resources_dedupes_cluster_members(mocker):
    """A multi-node Aurora cluster triggers one cluster stop, not one per member."""
    r = _make_rds(mocker)
    mocker.patch.object(r, "list", return_value=[
        {"Identifier": "writer", "Engine": 9, "ClusterIdentifier": "duploclus1"},
        {"Identifier": "reader", "Engine": 9, "ClusterIdentifier": "duploclus1"},
        {"Identifier": "plain", "Engine": 1, "InstanceStatus": "available"},
    ])
    r.stop_resources()
    posted = [c.args[0] for c in r.client.post.call_args_list]
    assert posted == [
        "v3/subscriptions/tid-1/aws/rds/cluster/duploclus1/stop",
        "v3/subscriptions/tid-1/aws/rds/instance/duploplain/stop",
    ]


@pytest.mark.unit
@pytest.mark.rds
def test_stop_resources_honors_exclude(mocker):
    """Excluded instance identifiers are left untouched."""
    r = _make_rds(mocker)
    mocker.patch.object(r, "list", return_value=[
        {"Identifier": "keep", "Engine": 1, "InstanceStatus": "available"},
        {"Identifier": "skip", "Engine": 1, "InstanceStatus": "available"},
    ])
    r.stop_resources(exclude=["duploskip"])
    posted = [c.args[0] for c in r.client.post.call_args_list]
    assert posted == [
        "v3/subscriptions/tid-1/aws/rds/instance/duplokeep/stop"
    ]


@pytest.mark.unit
@pytest.mark.rds
def test_stop_resources_swallows_benign_state_error(mocker):
    """An 'already stopping' cluster error is benign — no genuine error returned."""
    r = _make_rds(mocker)
    mocker.patch.object(r, "list", return_value=[
        {"Identifier": "writer", "Engine": 9, "ClusterIdentifier": "duploclus1"},
        {"Identifier": "plain", "Engine": 1, "InstanceStatus": "available"},
    ])
    r.client.post.side_effect = [
        DuploError("InvalidDBClusterStateException: already stopping", 400),
        MagicMock(),
    ]
    errors = r.stop_resources()
    # Both attempted; the benign one is logged but not reported as a failure.
    assert r.client.post.call_count == 2
    assert errors == []
    r.duplo.logger.warning.assert_called()


@pytest.mark.unit
@pytest.mark.rds
def test_stop_resources_collects_genuine_error_and_continues(mocker):
    """A genuine (non-benign, non-transient) error is collected; sweep continues."""
    r = _make_rds(mocker)
    mocker.patch.object(r, "list", return_value=[
        {"Identifier": "clus", "Engine": 9, "ClusterIdentifier": "duploclus1"},
        {"Identifier": "plain", "Engine": 1, "InstanceStatus": "available"},
    ])
    boom = DuploError("500 Internal Server Error", 500)  # non-transient
    r.client.post.side_effect = [boom, MagicMock()]
    errors = r.stop_resources()
    # The plain instance was still attempted after the cluster failed...
    assert r.client.post.call_count == 2
    # ...and the genuine failure is reported back to the caller, not swallowed.
    assert len(errors) == 1
    assert errors[0][0] == "duploclus"
    assert errors[0][1] is boom


@pytest.mark.unit
@pytest.mark.rds
def test_stop_resources_retries_transient_then_succeeds(mocker):
    """A transient 503 is retried, and the resource stops on the retry."""
    mocker.patch("duplocloud.resource.time.sleep")  # no real backoff
    r = _make_rds(mocker)
    mocker.patch.object(r, "list", return_value=[
        {"Identifier": "plain", "Engine": 1, "InstanceStatus": "available"},
    ])
    r.client.post.side_effect = [
        DuploError("503 Service Unavailable", 503),  # first attempt fails
        MagicMock(),                                  # retry succeeds
    ]
    errors = r.stop_resources()
    assert r.client.post.call_count == 2
    assert errors == []


@pytest.mark.unit
@pytest.mark.rds
def test_stop_resources_records_persistent_transient_failure(mocker):
    """A 503 that never clears is retried, then recorded as a genuine failure."""
    mocker.patch("duplocloud.resource.time.sleep")
    r = _make_rds(mocker)
    mocker.patch.object(r, "list", return_value=[
        {"Identifier": "plain", "Engine": 1, "InstanceStatus": "available"},
    ])
    r.client.post.side_effect = DuploError("503 Service Unavailable", 503)
    errors = r.stop_resources()
    assert r.client.post.call_count == 3  # default attempts
    assert len(errors) == 1
    assert errors[0][0] == "duploplain"
