
import requests
from cachetools import cached, TTLCache
from importlib.metadata import entry_points
import os

ENTRYPOINT="duplocloud.net"

class DuploClient():
    
  def __init__(self, host, token, tenant="default", args=[]) -> None:
    self.host = host
    self.timeout = 10
    self.args = args
    self.tenant = tenant
    self.headers = {
      'Content-Type': 'application/json',
      'Authorization': f"Bearer {token}"
    }
  
  def __str__(self) -> str:
     return f"""
Client for Duplo at {self.host}
"""

  @cached(cache=TTLCache(maxsize=128, ttl=60))
  def get(self, path):
    response = requests.get(
      url=f"{self.host}/{path}",
      headers=self.headers,
      timeout=self.timeout
    )
    return response.json()
  
  def post(self, path, data={}):
    return requests.post(
      url=f"{self.host}/{path}",
      headers=self.headers,
      timeout=self.timeout,
      json=data
    )
  
  def service(self, name):
    """Load Service
      
    Load a Service class from the entry points.
    Args:
      name: The name of the service.
    Returns:
      The callable krm function
    """
    eps = entry_points()[ENTRYPOINT]
    # e = entry_points(group=group, name=kind)
    e = [ep for ep in eps if ep.name == name][0]
    svc = e.load() 
    return svc(self)