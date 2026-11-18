from datetime import datetime, timezone

import pytest

from duplo_resource.service import DuploService
from duplo_resource.service_rollout import RolloutBaseline
from duplocloud.errors import DuploFailedResource, DuploStillWaiting

pytestmark = pytest.mark.unit

T0 = datetime(2026, 11, 18, 20, 0, 0, tzinfo=timezone.utc)
BASELINE = RolloutBaseline(frozenset({"rs-old"}), T0)
UPDATES = {"Name": "web", "Image": "nginx:1.27.5"}


def _pod(rs, created="2026-11-18T20:00:30Z", cur=1, des=1, image="nginx:1.27.5"):
  return {
    "InstanceId": f"{rs}-x",
    "ControlledBy": {"NativeId": rs},
    "CreationTimestamp": created,
    "CurrentStatus": cur,
    "DesiredStatus": des,
    "Containers": [{"Image": image}],
  }


def _service(**extra):
  return {
    "Name": "web",
    "Replicas": 2,
    "ReplicasActive": 2,
    "Template": {
      "Cloud": 0,
      "OtherDockerConfig": "{}",
      "Containers": [{"Name": "web", "Image": "nginx:1.27"}],
    },
    **extra,
  }


@pytest.fixture
def check_for(mocker):
  """Build a wait_check for the given pods, then return it for calling."""
  def build(pods, old=None, updates=UPDATES, baseline=BASELINE,
            restart=False, current=None, faults=None):
    old = old or _service()
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = True
    svc = DuploService(mock_duplo)
    svc._tenant = {"AccountName": "acct", "TenantId": "tid"}
    svc._tenant_id = "tid"
    svc.tenant_svc = mocker.MagicMock()
    svc.tenant_svc.faults.return_value = faults or []
    live = current or {
      **old, "Template": {**old["Template"],
        "Containers": [{"Name": "web", "Image": "nginx:1.27.5"}]},
    }
    mocker.patch.object(svc, "find", return_value=live)
    mocker.patch.object(svc, "pods", return_value=pods)
    wait = mocker.patch("duplocloud.resource.DuploResource.wait",
                        autospec=True)
    svc._wait(old, updates, baseline, restart=restart)
    return wait.call_args.args[1]
  return build


def test_same_digest_new_replicaset_completes(check_for):
  # new pods report the old tag, as the kubelet does for a shared digest
  pods = [_pod("rs-new", image="docker.io/library/nginx:1.27")] * 2
  check_for(pods)()


def test_old_pod_running_keeps_waiting(check_for):
  pods = [_pod("rs-new"), _pod("rs-new"), _pod("rs-old")]
  with pytest.raises(DuploStillWaiting, match=r"rollout: 2/2 new pods running, 1 old pods still running"):
    check_for(pods)()


def test_status3_window_keeps_waiting(check_for):
  pods = [_pod("rs-old", cur=3), _pod("rs-old", cur=3)]
  with pytest.raises(DuploStillWaiting, match=r"0/2 new pods running, 0 old"):
    check_for(pods)()


def test_reused_replicaset_counts_as_new(check_for):
  # rollback to a ReplicaSet that had no pods in the baseline
  pods = [_pod("rs-earlier"), _pod("rs-earlier")]
  check_for(pods)()


def test_restart_forces_rollover(check_for):
  # no image change, restart=True
  service = _service()
  pods = [_pod("rs-new"), _pod("rs-new"), _pod("rs-old")]
  with pytest.raises(DuploStillWaiting, match="1 old pods still running"):
    check_for(pods, old=service, updates=service, current=service,
              restart=True)()


def test_hpa_uses_min_replicas(check_for):
  # service without ReplicasActive, HPASpecs present
  old = _service(HPASpecs={"minReplicas": 2, "maxReplicas": 5})
  del old["ReplicasActive"]
  with pytest.raises(DuploStillWaiting, match=r"1/2 minimum new pods running"):
    check_for([_pod("rs-new")], old=old)()


def test_hpa_with_replicas_active_uses_active_count(check_for):
  old = _service(ReplicasActive=3,
                 HPASpecs={"minReplicas": 2, "maxReplicas": 5})
  with pytest.raises(DuploStillWaiting, match=r"2/3 new pods running"):
    check_for([_pod("rs-new")] * 2, old=old)()


def test_zero_replicas_completes(check_for):
  old = _service(Replicas=0, ReplicasActive=0)
  check_for([], old=old)()


def test_missing_controlled_by_uses_image_check(check_for):
  # one pod without ControlledBy: the image path runs and ignores the old-tag pod
  pods = [_pod("rs-new", image="nginx:1.27.5"),
          {**_pod("x", image="nginx:1.27"), "ControlledBy": None}]
  with pytest.raises(DuploStillWaiting, match=r"waiting for pods 1/2"):
    check_for(pods)()


def test_no_baseline_uses_image_check(check_for):
  # baseline=None keeps today's behaviour: old-tag pods are ignored
  pods = [_pod("rs-new", image="docker.io/library/nginx:1.27")] * 2
  with pytest.raises(DuploStillWaiting, match=r"waiting for pods 0/2"):
    check_for(pods, baseline=None)()


def test_formatting_only_conf_change_is_not_rollover(check_for):
  old = _service()
  old["Template"]["OtherDockerConfig"] = '{\n  "A": 1\n}'
  updates = {"Name": "web", "OtherDockerConfig": '{"A": 1}'}
  pods = [_pod("rs-old"), _pod("rs-old")]
  check_for(pods, old=old, updates=updates, current=old)()


def test_pod_fault_raises(check_for):
  faults = [{"Resource": {"Name": "rs-new-x"}, "Description": "CrashLoopBackOff"}]
  pods = [_pod("rs-new"), _pod("rs-new")]
  with pytest.raises(DuploFailedResource, match="CrashLoopBackOff"):
    check_for(pods, faults=faults)()


def test_old_pod_fault_is_ignored(check_for):
  # an old pod crash-looping must not fail a wait that is fixing it
  faults = [{"Resource": {"Name": "rs-old-x"}, "Description": "OOMKilled"}]
  pods = [_pod("rs-new"), _pod("rs-new"), _pod("rs-old", cur=3)]
  check_for(pods, faults=faults)()


def test_conf_change_is_rollover(check_for):
  old = _service()
  old["Template"]["OtherDockerConfig"] = '{"A": 1}'
  updates = {"Name": "web", "OtherDockerConfig": '{"A": 2}'}
  current = _service()
  current["Template"]["OtherDockerConfig"] = '{"A": 2}'
  pods = [_pod("rs-new"), _pod("rs-new"), _pod("rs-old")]
  with pytest.raises(DuploStillWaiting, match="1 old pods still running"):
    check_for(pods, old=old, updates=updates, current=current)()


def test_legacy_path_skips_baseline_replicaset_pods(check_for):
  # a pod without CreationTimestamp forces the legacy image path; the old
  # ReplicaSet's running pod must not count towards the replicas
  service = _service()
  pods = [{**_pod("rs-new"), "CreationTimestamp": None}, _pod("rs-old")]
  with pytest.raises(DuploStillWaiting, match=r"waiting for pods 1/2"):
    check_for(pods, old=service, updates=service, current=service,
              restart=True)()
