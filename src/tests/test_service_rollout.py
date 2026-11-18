from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from duplo_resource.service_rollout import (
  RolloutBaseline,
  RolloutCounts,
  count_rollout,
  is_new_pod,
  replicasets_of,
  server_time,
  tracks_replicasets,
)

pytestmark = pytest.mark.unit

T0 = datetime(2026, 11, 18, 20, 0, 0, tzinfo=timezone.utc)


def _pod(rs, created="2026-11-18T20:00:30Z", cur=1, des=1):
  return {
    "InstanceId": f"{rs}-x",
    "ControlledBy": {"NativeId": rs},
    "CreationTimestamp": created,
    "CurrentStatus": cur,
    "DesiredStatus": des,
  }


def test_replicasets_of_skips_pods_without_owner():
  pods = [_pod("rs-a"), _pod("rs-b"), {"InstanceId": "x"}]
  assert replicasets_of(pods) == frozenset({"rs-a", "rs-b"})


def test_server_time_parses_date_header():
  resp = SimpleNamespace(headers={"Date": "Wed, 18 Nov 2026 20:00:00 GMT"})
  assert server_time(resp) == T0


def test_server_time_missing_header():
  assert server_time(SimpleNamespace(headers={})) is None
  assert server_time(MagicMock()) is None


def test_new_replicaset_created_after_start_is_new():
  assert is_new_pod(_pod("rs-new"), RolloutBaseline(frozenset({"rs-old"}), T0))


def test_baseline_replicaset_is_old():
  assert not is_new_pod(_pod("rs-old"), RolloutBaseline(frozenset({"rs-old"}), T0))


def test_pod_created_before_start_minus_skew_is_old():
  pod = _pod("rs-new", created="2026-11-18T19:59:54Z")
  assert not is_new_pod(pod, RolloutBaseline(frozenset({"rs-old"}), T0))


def test_pod_created_within_skew_is_new():
  pod = _pod("rs-new", created="2026-11-18T19:59:56Z")
  assert is_new_pod(pod, RolloutBaseline(frozenset({"rs-old"}), T0))


def test_is_new_without_started_at():
  pod = _pod("rs-new", created="2020-01-01T00:00:00Z")
  assert is_new_pod(pod, RolloutBaseline(frozenset({"rs-old"})))


def test_tracks_replicasets():
  assert tracks_replicasets([])
  assert tracks_replicasets([_pod("rs-a")])
  assert not tracks_replicasets([_pod("rs-a"), {"InstanceId": "x", "CreationTimestamp": "2026-11-18T20:00:30Z"}])


def test_count_rollout_ignores_pods_that_are_not_running():
  base = RolloutBaseline(frozenset({"rs-old"}), T0)
  pods = [_pod("rs-new"), _pod("rs-new", cur=3), _pod("rs-old"), _pod("rs-old", cur=3)]
  assert count_rollout(pods, base) == RolloutCounts(new_running=1, old_running=1)
