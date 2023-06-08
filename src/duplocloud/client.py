
import requests
import json
from cachetools import cached, TTLCache
from importlib.metadata import entry_points

ENTRYPOINT="duplocloud.net"

class DuploClient():
  """Duplo Client

  This is the main Duplo client class. It is used to connect to Duplo and
  to retrieve resources from Duplo. All services have a reference to this
  when they are created.

  Example: Using injected client to load a service.
      ```python
      from duplocloud.client import DuploClient  
      from duplocloud.resource import DuploResource  
      from duplocloud.errors import DuploError  

      class DuploSomeService(DuploResource):
        def __init__(self, duplo: DuploClient):
          super().__init__(duplo)
          self.tenent_svc = duplo.service('tenant')
      ```
  """
    
  def __init__(self, host, token, tenant_name="default", args=[]) -> None:
    self.host = host
    self.timeout = 10
    self.args = args
    self.tenant_name = tenant_name
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
    """Get a Duplo resource.

    This request is cached for 60 seconds.
    
    Args:
      path: The path to the resource.
    Returns:
      The resource as a JSON object.
    """
    response = requests.get(
      url = f"{self.host}/{path}",
      headers = self.headers,
      timeout = self.timeout
    )
    return response.json()
  
  def post(self, path, data={}):
    """Post data to a Duplo resource.
    
    Args:
      path: The path to the resource.
      data: The data to post.
    Returns:
      The response as a JSON object.
    """
    return requests.post(
      url = f"{self.host}/{path}",
      headers = self.headers,
      timeout = self.timeout,
      json = data
    )
  
  def service(self, name):
    """Load Service
      
    Load a Service class from the entry points.

    Args:
      name: The name of the service.
    Returns:
      The instantiated service with a reference to this client.
    """
    eps = entry_points()[ENTRYPOINT]
    # e = entry_points(group=group, name=kind)
    e = [ep for ep in eps if ep.name == name][0]
    svc = e.load() 
    return svc(self)
  
  def json(self, data):
    """Convert data to JSON.
    
    Args:
      data: The data to convert.
    Returns:
      The data as a JSON object.
    """
    return json.dumps(data)