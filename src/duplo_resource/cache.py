import json
import os
from datetime import datetime, timezone, timedelta
from duplocloud.commander import Resource
from duplocloud.errors import DuploExpiredCache

@Resource("cache", client=None)
class DuploCache():
  """Cache Resource

  Filesystem cache operations for storing and retrieving JSON data.
  """
  def __init__(self, duplo):
    self.duplo = duplo

  def get(self, key: str) -> dict:
    """Get a cached item from the cache directory.

    Args:
      key: The key of the item to get.

    Returns:
      The json content parsed as a dict.
    """
    fn = f"{self.duplo.cache_dir}/{key}.json"
    if not os.path.exists(fn):
      raise DuploExpiredCache(key)
    try:
      with open(fn, "r") as f:
        return json.load(f)
    except json.JSONDecodeError:
      raise DuploExpiredCache(key)

  def set(self, key: str, data: dict) -> None:
    """Set a cached item in the cache directory.

    Args:
      key: The key of the item to set.
      data: The data to set.
    """
    if not os.path.exists(self.duplo.cache_dir):
      os.makedirs(self.duplo.cache_dir)
    fn = f"{self.duplo.cache_dir}/{key}.json"
    with open(fn, "w") as f:
      json.dump(data, f)

  def key_for(self, name: str) -> str:
    """Get the cache key for the given name.

    Args:
      name: The name to get the cache key for.

    Returns:
      The cache key as a string.
    """
    h = self.duplo.host.split("://")[1].replace("/", "")
    parts = [h]
    if self.duplo.isadmin:
      parts.append("admin")
    parts.append(name)
    return ",".join(parts)

  def expiration(self, hours: int = 1) -> str:
    """Get the expiration time for the given number of hours.

    Args:
      hours: The number of hours to add to the current time.

    Returns:
      The expiration time as a string.
    """
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%S+00:00')

  def expired(self, exp: str = None) -> bool:
    """Check if the given expiration time is expired.

    Args:
      exp: The expiration time to check.

    Returns:
      True if the expiration time is in the past, False otherwise.
    """
    if exp is None:
      return True
    return datetime.now(timezone.utc) > datetime.fromisoformat(exp)
