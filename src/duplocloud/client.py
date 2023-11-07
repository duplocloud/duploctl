
import requests
import json
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
               service: t.SERVICE=None,
               command: t.COMMAND=None,
               query: t.QUERY=None,
               output: t.OUTPUT="json",
               version: t.VERSION=None,
               args=[]) -> None:
    self.host = host
    self.tenant = tenant
    self.service = service
    self.command = command
    self.query = query
    self.output = output
    self.args = args
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
  
  @staticmethod
  def from_env():
    """Create a DuploClient from environment variables.
    
    Returns:
      The DuploClient.
    """
    parser = get_parser(DuploClient.__init__)
    env, args = parser.parse_known_args()
    return DuploClient(**vars(env), args=args)


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
  
  def load(self, name: str=None):
    """Load Service
      
    Load a Service class from the entry points.

    Args:
      name: The name of the service.
    Returns:
      The instantiated service with a reference to this client.
    """
    # make sure we have a service to use
    if name is None and self.service is None:
      raise DuploError("No service name provided for client loader", 500)
    elif name is None and self.service is not None:
      name = self.service
    # load and instantiate from the entry points
    svc = load_service(name)
    return svc(self)

  
  def run(self, name: str=None, command: str=None, args: list=None):
    """Run a service command.
    
    Args:
      name: The name of the service.
      command: The command to run.
      args: The arguments to the command.
    Returns:
      The result of the command.
    """
    # make sure we have a command
    if command is None and self.command is None:
      raise DuploError("No command provided for client runner", 500)
    elif command is None and self.command is not None:
      command = self.command
    # make sure we have args to use
    if args is None:
      args = self.args # this already defaults to empty list
    # load and execute
    svc = self.load(name)
    res = svc.exec(command, args)
    if self.query:
      try:
        res = jmespath.search(self.query, res)
      except jmespath.exceptions.ParseError as e:
        raise DuploError("Invalid jmespath query", 500) from e
      except jmespath.exceptions.JMESPathTypeError as e:
        raise DuploError("Invalid jmespath query", 500) from e
    format = load_format(self.output)
    return format(res)
  
  def json(self, data: dict):
    """Convert data to JSON.
    
    Args:
      data: The data to convert.
    Returns:
      The data as a JSON object.
    """
    return json.dumps(data)
  
  def _validate_response(self, response):
    """Validate a response from Duplo.
    
    Args:
      response: The response to validate.
    Raises:
      DuploError: If the response was not 200. 
    Returns:
      The response as a JSON object.
    """
    contentType = response.headers['content-type'].split(';')[0]
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
    
