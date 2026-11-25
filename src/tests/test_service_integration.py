import time
import pytest
from duplocloud.errors import DuploNotFound, DuploStillWaiting
from .conftest import get_test_data

NAME = "duploctl-rollout"
REPLICAS = 2


@pytest.fixture(scope="class")
def service_resource(duplo):
    """Fixture to load the Service resource with waiting enabled."""
    resource = duplo.load("service")
    prior = resource.duplo.wait
    resource.duplo.wait = True
    yield resource
    resource.duplo.wait = prior


def running_replicasets(svc, name) -> dict:
    """Running pod count per ReplicaSet (CurrentStatus == DesiredStatus == 1)."""
    counts = {}
    for pod in svc.pods(name):
        if pod.get("CurrentStatus") == 1 and pod.get("DesiredStatus") == 1:
            rs = (pod.get("ControlledBy") or {}).get("NativeId")
            counts[rs] = counts.get(rs, 0) + 1
    return counts


def wait_for_rollout_ready(svc, name, replicas, timeout=300):
    """Poll until `replicas` pods run. create --wait does not wait for pods."""
    deadline = time.time() + timeout
    counts = {}
    while time.time() < deadline:
        counts = running_replicasets(svc, name)
        if sum(counts.values()) >= replicas:
            return counts
        time.sleep(10)
    pytest.fail(f"Service '{name}' did not reach {replicas} running pods in {timeout}s: {counts}")


def print_images(svc, name):
    for pod in svc.pods(name):
        containers = pod.get("Containers") or [{}]
        print(f"pod {pod.get('InstanceId')} rs={(pod.get('ControlledBy') or {}).get('NativeId')} "
              f"status={pod.get('CurrentStatus')}/{pod.get('DesiredStatus')} image={containers[0].get('Image')}")


def assert_replaced(svc, name, baseline_rs, replicas):
    """Every running pod belongs to a new ReplicaSet and the count is `replicas`."""
    counts = running_replicasets(svc, name)
    print_images(svc, name)
    old = set(counts) & set(baseline_rs)
    assert not old, f"pods still running from old ReplicaSets {old}: {counts}"
    assert sum(counts.values()) == replicas, f"expected {replicas} running pods, got {counts}"


@pytest.mark.integration
@pytest.mark.k8s
@pytest.mark.service
class TestServiceRollout:

    @pytest.fixture(autouse=True)
    def _restore_timeout(self, service_resource):
        prior = service_resource.duplo.wait_timeout
        service_resource.duplo.wait_timeout = 300
        yield
        service_resource.duplo.wait_timeout = prior

    @pytest.mark.dependency(name="create_rollout_service", depends=["asg_restored"], scope="session")
    @pytest.mark.order(66)
    def test_create_rollout_service(self, service_resource):
        """Create the service with a readiness probe and two replicas."""
        r = service_resource
        try:
            existing = r.find(NAME)
        except DuploNotFound:
            existing = None
        if existing:
            print(f"Service '{NAME}' exists, deleting before recreate")
            r.delete(NAME)
            deadline = time.time() + 300
            while True:
                try:
                    r.find(NAME)
                except DuploNotFound:
                    break
                if time.time() >= deadline:
                    pytest.fail(f"Service '{NAME}' still present 300s after delete")
                time.sleep(10)
        r.create(body=get_test_data("service-rollout"))
        wait_for_rollout_ready(r, NAME, REPLICAS)

    @pytest.mark.dependency(depends=["create_rollout_service"], scope="session")
    @pytest.mark.order(67)
    def test_update_image_same_digest(self, service_resource):
        """DUPLO-45146: tag change to the same digest must not hang the wait."""
        r = service_resource
        baseline = running_replicasets(r, NAME)
        # nginx 1.27 is end-of-life, so the tags nginx:1.27 and nginx:1.27.5 stay on one
        # digest. If they ever diverge this test still passes but no longer exercises
        # the same-digest path. Digests are not pinned: that would not reproduce the
        # tag-versus-digest mismatch the bug depends on.
        r.update_image(NAME, "nginx:1.27.5")
        assert_replaced(r, NAME, baseline, REPLICAS)

    @pytest.mark.dependency(depends=["create_rollout_service"], scope="session")
    @pytest.mark.order(68)
    def test_restart_waits_for_new_pods(self, service_resource):
        """restart --wait must return only once replacement pods run."""
        r = service_resource
        baseline = running_replicasets(r, NAME)
        r.restart(NAME)
        assert_replaced(r, NAME, baseline, REPLICAS)

    @pytest.mark.dependency(depends=["create_rollout_service"], scope="session")
    @pytest.mark.order(69)
    def test_update_image_new_image(self, service_resource):
        """A different digest: the wait must outlast the readiness delay."""
        r = service_resource
        baseline = running_replicasets(r, NAME)
        r.update_image(NAME, "nginx:1.28")
        assert_replaced(r, NAME, baseline, REPLICAS)

    @pytest.mark.dependency(depends=["create_rollout_service"], scope="session")
    @pytest.mark.order(70)
    def test_never_ready_image_times_out(self, service_resource):
        """An image that never becomes ready must time out, not succeed."""
        r = service_resource
        r.duplo.wait_timeout = 180
        with pytest.raises(DuploStillWaiting, match="Timed out waiting"):
            r.update_image(NAME, "registry.k8s.io/pause:3.10")

    @pytest.mark.dependency(depends=["create_rollout_service"], scope="session")
    @pytest.mark.order(71)
    def test_rollback_after_failed_rollout(self, service_resource):
        """Rolling back to the serving image reuses its ReplicaSet and completes."""
        r = service_resource
        baseline = running_replicasets(r, NAME)
        assert baseline, "expected the nginx:1.28 ReplicaSet to still be serving"
        pause_rs = set()
        for pod in r.pods(NAME):
            containers = pod.get("Containers") or [{}]
            if "pause" in (containers[0].get("Image") or ""):
                pause_rs.add((pod.get("ControlledBy") or {}).get("NativeId"))
        r.update_image(NAME, "nginx:1.28")
        counts = running_replicasets(r, NAME)
        print_images(r, NAME)
        assert set(counts) <= set(baseline), f"unexpected ReplicaSets running: {counts} (baseline {baseline})"
        assert not (set(counts) & pause_rs), f"pause ReplicaSet still running: {counts}"
        assert sum(counts.values()) == REPLICAS, f"expected {REPLICAS} running pods, got {counts}"

    @pytest.mark.dependency(depends=["create_rollout_service"], scope="session")
    @pytest.mark.order(993)
    def test_delete_rollout_service(self, service_resource):
        """Delete the service."""
        response = service_resource.delete(NAME)
        assert "deleted" in response["message"].lower()
