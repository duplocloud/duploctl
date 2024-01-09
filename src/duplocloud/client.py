
import requests
import jmespath
from cachetools import cached, TTLCache
from .errors import DuploError
from .commander import load_service,load_format, Command, get_parser
from . import args as t

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
  @Command()
  def __init__(self, 
               host: t.HOST, 
               token: t.TOKEN, 
               tenant: t.TENANT,
               query: t.QUERY=None,
               output: t.OUTPUT="json",
               version: t.VERSION=None) -> None:
    self.host = host
    self.tenant = tenant
    self.query = query
    self.output = output
    self.timeout = 10
    self.version = version
    self.headers = {
      'Content-Type': 'application/json',
      'Authorization': f"Bearer {token}"
    }
  
  def __str__(self) -> str:
     return f"""
Client for Duplo at {self.host}
"""
  
  def __call__(self, resource: str, *args):
    """Run a service command.
    
    Args:
      resource: The name of the resource.
      command: The command to run.
      args: The arguments to the command.
    Returns:
      The result of the command.
    """
    res = self.load(resource)
    data = res(*args)
    data = self.filter(data)
    return self.format(data)
  
  @staticmethod
  def from_env():
    """Create a DuploClient from environment variables.
    
    Returns:
      The DuploClient.
    """
    parser = get_parser(DuploClient.__init__)
    env, args = parser.parse_known_args()
    return DuploClient(**vars(env)), args

  @cached(cache=TTLCache(maxsize=128, ttl=60))
  def get(self, path: str):
    """Get a Duplo resource.

    This request is cached for 60 seconds.
    
    Args:
      path: The path to the resource.
    Returns:
      The resource as a JSON object.
    """
    try:
      response = requests.get(
        url = f"{self.host}/{path}",
        headers = self.headers,
        timeout = self.timeout
      )
    except requests.exceptions.Timeout as e:
      raise DuploError("Timeout connecting to Duplo", 500) from e
    except requests.exceptions.ConnectionError as e:
      raise DuploError("A conntection error occured with Duplo", 500) from e
    except requests.exceptions.RequestException as e:
      raise DuploError("Error connecting to Duplo with a request exception", 500) from e
    return self._validate_response(response)
  
  def post(self, path: str, data: dict={}):
    """Post data to a Duplo resource.
    
    Args:
      path: The path to the resource.
      data: The data to post.
    Returns:
      The response as a JSON object.
    """
    response = requests.post(
      url = f"{self.host}/{path}",
      headers = self.headers,
      timeout = self.timeout,
      json = data
    )
    return self._validate_response(response)
  
  def put(self, path: str, data: dict={}):
    """Put data to a Duplo resource.
    
    Args:
      path: The path to the resource.
      data: The data to post.
    Returns:
      The response as a JSON object.
    """
    response = requests.put(
      url = f"{self.host}/{path}",
      headers = self.headers,
      timeout = self.timeout,
      json = data
    )
    return self._validate_response(response)
  
  def load(self, resource: str):
    """Load Service
      
    Load a Service class from the entry points.

    Args:
      name: The name of the service.
    Returns:
      The instantiated service with a reference to this client.
    """
    # load and instantiate from the entry points
    svc = load_service(resource)
    return svc(self)
  
  def filter(self, data: dict):
    """Query data

    Uses the jmespath library to query data.
    Set the query to use on the property. 
    
    Args:
      data: The data to query.
    Returns:
      The queried data.
    """
    if not self.query:
      return data
    try:
      return jmespath.search(self.query, data)
    except jmespath.exceptions.ParseError as e:
      raise DuploError("Invalid jmespath query", 500) from e
    except jmespath.exceptions.JMESPathTypeError as e:
      raise DuploError("Invalid jmespath query", 500) from e
  
  def format(self, data: dict):
    """Format data.
    
    Args:
      data: The data to format.
    Returns:
      The data as a string.
    """
    fmt = load_format(self.output)
    return fmt(data)
  
  def _validate_response(self, response: dict):
    """Validate a response from Duplo.
    
    Args:
      response: The response to validate.
    Raises:
      DuploError: If the response was not 200. 
    Returns:
      The response as a JSON object.
    """
    contentType = response.headers.get('content-type', 'application/json').split(';')[0]
    if 200 <= response.status_code < 300:
      if contentType == 'application/json':
        return response.json()
      elif contentType == 'text/plain':
        return {"message": response.text}
    
    if response.status_code == 404:
      raise DuploError("Resource not found", response.status_code)
    
    if response.status_code == 401:
      raise DuploError(response.text, response.status_code)

    raise DuploError("Duplo responded with an error", response.status_code)
    
