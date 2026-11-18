"""Classify a service's pods into old and new for rollout waits.

A rollout is identified by ReplicaSet rather than image tag. Pods whose
ReplicaSet was not present before the change (and, when the server time is
known, that were created no earlier than the start minus a small skew) are
new. A pod of a baseline ReplicaSet also counts as new when a rollout was
still in progress (several baseline ReplicaSets), the main image changed, and
the pod reports the new image: Kubernetes reuses that ReplicaSet on rollback.
The rollout is finished once the new pods run and no old pod remains, where
an old pod remains unless it is terminal (Duplo reports Ready pods as pending
for a while after a change, and they still serve traffic). Kubernetes only
scales an old ReplicaSet down as new pods become available.
"""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import NamedTuple, Optional

START_SKEW = timedelta(seconds=5)
TERMINAL_STATUSES = (6, 7, 11)


@dataclass(frozen=True)
class RolloutBaseline:
  """The state of a service captured before a change is sent.

  Attributes:
    replicasets: ReplicaSet names owning the pods before the change.
    started_at: Server time of the change, or None when unknown.
    image: The new main image when it changed, or None. Enables the rollback
      exception of is_new_pod.
  """
  replicasets: frozenset[str]
  started_at: Optional[datetime] = None
  image: Optional[str] = None


class RolloutCounts(NamedTuple):
  """Running pod counts split by new and old ReplicaSets."""
  new_running: int
  old_remaining: int


def _owner(pod: dict) -> Optional[str]:
  return (pod.get("ControlledBy") or {}).get("NativeId")


def normalize_image(image: str) -> str:
  """Remove Docker registry prefixes from an image name."""
  return image.removeprefix("docker.io/library/").removeprefix("docker.io/").removeprefix("library/")


def is_terminal(pod: dict) -> bool:
  """Tell whether a pod is gone or going (status 6, 7 or 11)."""
  return (pod.get("CurrentStatus") in TERMINAL_STATUSES
          or pod.get("DesiredStatus") in TERMINAL_STATUSES)


def replicasets_of(pods: list[dict]) -> frozenset[str]:
  """Return the ReplicaSet names that own the given non-terminal pods.

  Args:
    pods: Pods as returned by the Duplo API.

  Returns:
    The set of ControlledBy.NativeId values of non-terminal pods that have one.
  """
  return frozenset(rs for p in pods if not is_terminal(p) if (rs := _owner(p)))


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
    True when all pods carry both fields and the creation time parses,
    including for an empty list.
  """
  try:
    return all(_owner(p) and _created(p) for p in pods)
  except (ValueError, TypeError, AttributeError):
    return False


def is_running(pod: dict) -> bool:
  """Tell whether a pod is running and meant to be."""
  return pod.get("CurrentStatus") == 1 and pod.get("DesiredStatus") == 1


def _created(pod: dict) -> datetime:
  # Python 3.10 accepts only 3 or 6 fraction digits, so pad or truncate to 6
  text = re.sub(r"\.(\d+)", lambda m: "." + m.group(1)[:6].ljust(6, "0"),
                pod["CreationTimestamp"].replace("Z", "+00:00"))
  parsed = datetime.fromisoformat(text)
  return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _image(pod: dict) -> Optional[str]:
  try:
    return normalize_image(pod["Containers"][0]["Image"])
  except (KeyError, IndexError, TypeError, AttributeError):
    return None


def is_new_pod(pod: dict, baseline: RolloutBaseline) -> bool:
  """Tell whether a pod belongs to the rollout rather than the baseline.

  Args:
    pod: A pod as returned by the Duplo API.
    baseline: The state captured before the change.

  Returns:
    True when its ReplicaSet is not in the baseline and, if the start time
    is known, it was created no earlier than the start minus START_SKEW. Also
    True for a pod of a baseline ReplicaSet reporting the new image when the
    baseline holds more than one ReplicaSet (rollback mid-rollout).
  """
  if _owner(pod) in baseline.replicasets:
    return (baseline.image is not None
            and len(baseline.replicasets) > 1
            and _image(pod) == normalize_image(baseline.image))
  if baseline.started_at is None:
    return True
  return _created(pod) >= baseline.started_at - START_SKEW


def count_rollout(pods: list[dict], baseline: RolloutBaseline) -> RolloutCounts:
  """Count running new pods and old pods that remain.

  Args:
    pods: Pods as returned by the Duplo API.
    baseline: The state captured before the change.

  Returns:
    The number of running new pods and of old pods that are not terminal.
  """
  new_running = 0
  old_remaining = 0
  for p in pods:
    if is_new_pod(p, baseline):
      new_running += is_running(p)
    elif not is_terminal(p):
      old_remaining += 1
  return RolloutCounts(new_running=new_running, old_remaining=old_remaining)
