from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from duplo_resource.service_rollout import (
  RolloutBaseline,
  RolloutCounts,
  count_rollout,
  is_new_pod,
  is_terminal,
  normalize_image,
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


def test_count_rollout_counts_non_terminal_old_pods():
  base = RolloutBaseline(frozenset({"rs-old"}), T0)
  pods = [
    _pod("rs-new"), _pod("rs-new", cur=3),
    _pod("rs-old"), _pod("rs-old", cur=3), _pod("rs-old", cur=6),
    _pod("rs-old", des=7),
  ]
  assert count_rollout(pods, base) == RolloutCounts(new_running=1, old_remaining=2)


def test_is_terminal():
  assert is_terminal(_pod("rs", cur=6))
  assert is_terminal(_pod("rs", cur=1, des=7))
  assert is_terminal(_pod("rs", cur=11))
  assert not is_terminal(_pod("rs", cur=3))


def test_replicasets_of_skips_terminal_pods():
  pods = [_pod("rs-a"), _pod("rs-b", cur=6), _pod("rs-c", des=11)]
  assert replicasets_of(pods) == frozenset({"rs-a"})


def test_normalize_image():
  assert normalize_image("docker.io/library/nginx:1") == "nginx:1"
  assert normalize_image("docker.io/acme/web:1") == "acme/web:1"
  assert normalize_image("library/nginx:1") == "nginx:1"


def _img_pod(rs, image):
  return {**_pod("x"), "ControlledBy": {"NativeId": rs}, "Containers": [{"Image": image}]}


def test_rollback_pod_of_baseline_replicaset_is_new():
  base = RolloutBaseline(frozenset({"rs-good", "rs-bad"}), T0, "nginx:1.27.5")
  pod = _img_pod("rs-good", "docker.io/library/nginx:1.27.5")
  assert is_new_pod(pod, base)
  assert not is_new_pod(_img_pod("rs-bad", "nginx:1.28"), base)


def test_single_replicaset_baseline_with_same_image_is_old():
  base = RolloutBaseline(frozenset({"rs-old"}), T0, "nginx:1.27.5")
  assert not is_new_pod(_img_pod("rs-old", "nginx:1.27.5"), base)


def test_rollback_exception_needs_image():
  base = RolloutBaseline(frozenset({"rs-good", "rs-bad"}), T0)
  assert not is_new_pod(_img_pod("rs-good", "nginx:1.27.5"), base)


def test_created_naive_timestamp_is_utc():
  base = RolloutBaseline(frozenset({"rs-old"}), T0)
  assert is_new_pod(_pod("rs-new", created="2026-11-18T20:00:30"), base)
  assert not is_new_pod(_pod("rs-new", created="2026-11-18T19:00:00"), base)


def test_created_long_fraction_parses():
  base = RolloutBaseline(frozenset({"rs-old"}), T0)
  pod = _pod("rs-new", created="2026-11-18T20:00:30.1234567Z")
  assert is_new_pod(pod, base)
  assert tracks_replicasets([pod])


def test_unparsable_timestamp_is_not_tracked():
  assert not tracks_replicasets([_pod("rs-a", created="garbage")])


def test_server_time_garbage_date():
  assert server_time(SimpleNamespace(headers={"Date": "garbage"})) is None


def test_missing_timestamp_key_is_not_tracked():
  assert not tracks_replicasets([{"ControlledBy": {"NativeId": "rs"}}])
