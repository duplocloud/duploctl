"""Classify a service's pods into old and new for rollout waits.

A rollout is identified by ReplicaSet rather than image tag. Pods whose
ReplicaSet was not present before the change (and, when the server time is
known, that were created no earlier than the start minus a small skew) are
new. The rollout is finished once the new pods run and no old pod does, since
Kubernetes only scales an old ReplicaSet down as new pods become available.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import NamedTuple, Optional

START_SKEW = timedelta(seconds=5)


@dataclass(frozen=True)
class RolloutBaseline:
  """The state of a service captured before a change is sent.

  Attributes:
    replicasets: ReplicaSet names owning the pods before the change.
    started_at: Server time of the change, or None when unknown.
  """
  replicasets: frozenset[str]
  started_at: Optional[datetime] = None


class RolloutCounts(NamedTuple):
  """Running pod counts split by new and old ReplicaSets."""
  new_running: int
  old_running: int


def _owner(pod: dict) -> Optional[str]:
  return (pod.get("ControlledBy") or {}).get("NativeId")


def replicasets_of(pods: list[dict]) -> frozenset[str]:
  """Return the ReplicaSet names that own the given pods.

  Args:
    pods: Pods as returned by the Duplo API.

  Returns:
    The set of ControlledBy.NativeId values of pods that have one.
  """
  return frozenset(rs for rs in map(_owner, pods) if rs)


def server_time(response) -> Optional[datetime]:
  """Read the server time from a response's Date header.

  Args:
    response: An HTTP response with a headers mapping.

  Returns:
    A timezone-aware datetime, or None when the header is missing or invalid.
  """
  try:
    parsed = parsedate_to_datetime(response.headers["Date"])
  except (KeyError, TypeError, ValueError, AttributeError):
    return None
  if parsed is None or parsed.tzinfo is None:
    return None
  return parsed


def tracks_replicasets(pods: list[dict]) -> bool:
  """Tell whether every pod reports its ReplicaSet and creation time.

  Args:
    pods: Pods as returned by the Duplo API.

  Returns:
    True when all pods carry both fields, including for an empty list.
  """
  return all(_owner(p) and p.get("CreationTimestamp") for p in pods)


def is_running(pod: dict) -> bool:
  """Tell whether a pod is running and meant to be."""
  return pod.get("CurrentStatus") == 1 and pod.get("DesiredStatus") == 1


def _created(pod: dict) -> datetime:
  return datetime.fromisoformat(pod["CreationTimestamp"].replace("Z", "+00:00"))


def is_new_pod(pod: dict, baseline: RolloutBaseline) -> bool:
  """Tell whether a pod belongs to the rollout rather than the baseline.

  Args:
    pod: A pod as returned by the Duplo API.
    baseline: The state captured before the change.

  Returns:
    True when its ReplicaSet is not in the baseline and, if the start time
    is known, it was created no earlier than the start minus START_SKEW.
  """
  if _owner(pod) in baseline.replicasets:
    return False
  if baseline.started_at is None:
    return True
  return _created(pod) >= baseline.started_at - START_SKEW


def count_rollout(pods: list[dict], baseline: RolloutBaseline) -> RolloutCounts:
  """Count running new and old pods.

  Args:
    pods: Pods as returned by the Duplo API.
    baseline: The state captured before the change.

  Returns:
    The number of running new pods and running old pods.
  """
  running = [p for p in pods if is_running(p)]
  new = sum(1 for p in running if is_new_pod(p, baseline))
  return RolloutCounts(new_running=new, old_running=len(running) - new)
