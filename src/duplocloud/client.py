
import sys
import requests
import jmespath
import os
import yaml
import json
import jsonpatch
import logging
import traceback
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from cachetools import cachedmethod, TTLCache
from pathlib import Path
from .commander import load_resource,load_format
from .errors import DuploError, DuploExpiredCache
from .server import TokenServer
from . import args
from .commander import Command, get_parser, extract_args, available_resources, VERSION
from typing import TypeVar

T = TypeVar("T")

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
               host: args.HOST=None,
               token: args.TOKEN=None,
               tenant: args.TENANT=None,
               tenant_id: args.TENANT_ID=None,
               home_dir: args.HOME_DIR=None,
               config_file: args.CONFIG=None,
               cache_dir: args.CACHE_DIR=None,
               version: args.VERSION=False,
               interactive: args.INTERACTIVE=False,
               ctx: args.CONTEXT=None,
               nocache: args.NOCACHE=False,
               browser: args.BROWSER=None,
               isadmin: args.ISADMIN=False,
               query: args.QUERY=None,
               output: args.OUTPUT="json",
               loglevel: args.LOGLEVEL="WARN",
               wait: args.WAIT=False):
    """DuploClient Constructor
    
    Creates an instance of a duplocloud client configured for a certain portal. All of the arguments are optional and can be set in the environment or in the config file. The types of each ofthe arguments are annotated types that are used by argparse to create the command line arguments.

    Args:
      host: The host of the Duplo instance.
      token: The token to use for authentication.
      tenant: The tenant to use.
      tenant_id: The tenant id to use.
      home_dir: The home directory for the client.
      config_file: The config file for the client.
      cache_dir: The cache directory for the client.
      version: The version of the client.
      interactive: The interactive mode for the client.
      ctx: The context to use.
      nocache: The nocache flag for the client.
      browser: The browser to use for interactive login.
      isadmin: The admin flag for the client.
      query: The query to use.
      output: The output format for the client.
      loglevel: The log level for the client.

    Returns:
      duplo (DuploClient): An instance of a DuploClient.
    """
    # forces the given context to be used
    if ctx: 
      host = None
      token = None
    # ignore the given token with interactive mode
    if token and interactive: 
      token = None
    # if a tenant id was given, the tenant name must be ignored
    if tenant_id:
      tenant = None

    user_home = Path.home()
    self.home_dir = home_dir or f"{user_home}/.duplo"
    self.config_file = config_file or f"{self.home_dir}/config"
    self.cache_dir = cache_dir or f"{self.home_dir}/cache"
    self.__config = None
    self.__context = ctx
    self.__host = self.__sanitize_host(host)
    self.__token = token.strip() if token else token
    self.__tenant = tenant.strip().lower() if tenant else tenant
    self.tenantid = tenant_id.strip() if tenant_id else tenant_id
    self.version = version
    self.interactive = interactive
    self.nocache = nocache
    self.browser = browser
    self.isadmin = isadmin
    self.query = query.strip() if query else query
    self.output = output.strip()
    self.timeout = 60
    self.__ttl_cache = TTLCache(maxsize=128, ttl=10)
    self.loglevel = loglevel
    self.logger = self.logger_for()
    self.wait = wait

  @staticmethod
  def from_env():
    """From Environment

    Create a DuploClient from environment variables. This is the most common way to create a DuploClient.

    Usage: New Client From Environment
      ```python
      duplo, args = DuploClient.from_env()
      ```

    Returns:
      duplo (DuploClient): An instance of a DuploClient.
    """
    a = extract_args(DuploClient.__init__)
    p = get_parser(a)
    env, xtra = p.parse_known_args()
    duplo = DuploClient(**vars(env))
    return duplo, xtra
  
  @staticmethod
  def from_args(*args: str): 
    """DuploClient from Environment

    Create a DuploClient from an array of global client arguments. 

    Args:
      args: An array of global client arguments aligning with the DuploClient constructor.

    Returns:
      duplo (DuploClient): An instance of DuploConfig.
    """
    a = extract_args(DuploClient.__init__)
    p = get_parser(a)
    env = p.parse_args(args)
    duplo = DuploClient(**vars(env))
    return duplo
  
  @staticmethod
  def from_creds(host: str, token: str, tenant: str):
    """Create a DuploClient from credentials.
    
    Args:
      host: The host of the Duplo instance.
      token: The token to use for authentication.
      tenant: The tenant to use.

    Returns:  
      duplo (DuploClient): The DuploClient.
    """
    return DuploClient(host=host, token=token, tenant=tenant)

  @property
  def settings(self) -> dict:
    """Get Config

    Get the Duplo config as a dict. This is accessed as a lazy loaded property.

    Returns:
      settings: The config as a dict.
    """
    if self.__config is None:
      if not os.path.exists(self.config_file):
        raise DuploError("Duplo config not found", 500)
      with open(self.config_file, "r") as f:
        self.__config = yaml.safe_load(f)
    return self.__config
  
  @property
  def context(self) -> dict:
    """Get Config Context
    
    Get the current context from the Duplo config. This is accessed as a lazy loaded property. 

    Returns:
      The context as a dict.
    """
    s = self.settings
    ctx = self.__context if self.__context else s.get("current-context", None)
    if ctx is None:
      raise DuploError(
        "Duplo context not set, please set 'current-context' to a portals name in your config", 500)
    try:
      return [c for c in s["contexts"] if c["name"] == ctx][0]
    except IndexError:
      raise DuploError(f"Portal '{ctx}' not found in config", 500)
    
  @property
  def host(self) -> str:
    """Get Host
    
    Get the host from the Duplo config. This is accessed as a lazy loaded property. 
    If the host is some kind of falsey value, it will attempt to use the context.

    Returns:
      The host as a string.
    """
    if not self.__host:
      self.use_context()
    return self.__host
  
  @property 
  def token(self) -> str:
    """Get Token
    
    Returns the configured token. If interactive mode is enabled, an attempt will be made to get the token interactively. Ultimately, the token is required and if it is not set, an error will be raised.
    This is accessed as a lazy loaded property.

    Returns:
      The token as a string.
    """
    if not self.host:
      raise DuploError("Host for Duplo portal is required", 500)
    if not self.__token and self.interactive:
      self.__token = self.interactive_token()
    if not self.__token:
      raise DuploError("Token for Duplo portal is required", 500)
    return self.__token
  
  @property
  def tenant(self) -> str:
    """Get Tenant
    
    Get the tenant from the Duplo config. This is accessed as a lazy loaded property. 
    If the tenant is some kind of falsey value, it will attempt to use the context.

    Returns:
      The tenant as a string.
    """
    if not self.host:
      raise DuploError("Host for Duplo portal is required", 500)
    return self.__tenant
  
  @tenant.setter
  def tenant(self, value: str) -> None:
    """Set Tenant
    
    Set the tenant for this Duplo client. This will override the tenant in the config.

    Args:
      value: The tenant to set.
    """
    self.__tenant = value
  
  def __str__(self) -> str:
     return f"""
Host: {self.host}
Tenant: {self.tenant or self.tenantid}
Home: {self.home_dir}
Config: {self.config_file}
Cache: {self.cache_dir}
Version: {VERSION}
Path: {sys.argv[0]}
Available Resources: 
  {", ".join(available_resources())}
""".strip()
  
  def __call__(self, resource: str=None, *args):
    """Run a service command.
    
    Args:
      resource: The name of the resource.
      command: The command to run.
      args: The arguments to the command.
    Returns:
      The result of the command.
    """
    if not resource:
      raise DuploError(str(self), 400)
    r = self.load(resource)
    try:
      d = r(*args)
    except TypeError:
      if (r.__doc__):
        raise DuploError(r.__doc__, 400)
      else: 
        traceback.print_exc()
        raise DuploError(f"No docstring found, error calling command {resource} : Traceback printed", 400)

    if d is None:
      return None
    d = self.filter(d)
    return self.format(d)
  
  def logger_for(self, name: str=None) -> logging.Logger:
    """Create a Default Logger
    
    Create a default logger for the given name. This will create a logger with the name 'duplo' and add a console output handler.

    Args:
      name: The name of the logger.
    Returns:
      The logger.
    """
    n = "duplo"
    if name:
      n += f".{name}"
    logger = logging.getLogger(name)
    lvl = logging.getLevelName(self.loglevel)
    logger.setLevel(lvl)
    formatter = logging.Formatter("%(levelname)s %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    if (logger.hasHandlers()):
      logger.handlers.clear()
    logger.addHandler(handler)
    return logger

  @cachedmethod(lambda self: self.__ttl_cache)
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
        headers = self.__headers(),
        timeout = self.timeout
      )
    except requests.exceptions.Timeout as e:
      raise DuploError("Timeout connecting to Duplo", 500) from e
    except requests.exceptions.ConnectionError as e:
      raise DuploError("A conntection error occured with Duplo", 500) from e
    except requests.exceptions.RequestException as e:
      raise DuploError("Error connecting to Duplo with a request exception", 500) from e
    return self.__validate_response(response)
  
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
      headers = self.__headers(),
      timeout = self.timeout,
      json = data
    )
    return self.__validate_response(response)
  
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
      headers = self.__headers(),
      timeout = self.timeout,
      json = data
    )
    return self.__validate_response(response)
  
  def delete(self, path: str):
    """Delete a Duplo resource.
    
    Args:
      path: The path to the resource.
    Returns:
      The response as a JSON object.
    """
    response = requests.delete(
      url = f"{self.host}/{path}",
      headers = self.__headers(),
      timeout = self.timeout
    )
    return self.__validate_response(response)
  
  def jsonpatch(self, data, patches):
    """Json Patch
    
    Apply a json patch to a resource.

    Args:
      patches: The patches to apply.
    Returns:
      The patched resource as a JSON object.
    """
    try:
      return jsonpatch.apply_patch(data, patches)
    except jsonpatch.JsonPatchTestFailed as e:
      raise DuploError("JsonPatch test failed", 500) from e
    except jsonpatch.JsonPatchConflict as e:
      raise DuploError(f"JsonPatch conflict:\n {e}", 500)

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
    
  def load(self, kind: str) -> T:
    """Load Resource
      
    Load a resource class from the entry points.

    Args:
      kind: The name of the service.

    Returns:
      kind: The instantiated service with a reference to this client.
    """
    svc = load_resource(kind)
    return svc(self)
  
  def format(self, data: dict) -> str:
    """Format data.
    
    Args:
      data: The data to format.
    Returns:
      The data as a string.
    """
    fmt = load_format(self.output)
    return fmt(data)
  
  def use_context(self, name: str = None) -> None:
    """Use Context
    
    Use the specified context from the Duplo config.

    Args:
      name: The name of the context to use.
    """

    # Get the right context
    if name:
      self.__context = name
    ctx = self.context

    # set the context into this config
    self.__host = self.__sanitize_host(ctx.get("host", None))
    self.__token = ctx.get("token", None)
    self.__tenant = ctx.get("tenant", self.__tenant)
    self.interactive = ctx.get("interactive", False)
    self.isadmin = ctx.get("admin", False)
    self.nocache = ctx.get("nocache", False)
    # only tenant can be overridden by the args/env
    
  def get_cached_item(self, key: str) -> dict:
    """Get Cached Item
    
    Get a cached item from the cache directory. The files are all json. 
    This checks if the file exists and raises an expired cache if it does not. 
    Finally the file is read and returned as a JSON object. If anything goes wrong, an expired cache is raised because it's easy enough to rebuild it than to try and fix it.

    Args:
      name: The name of the item to get.

    Returns:
      The json content parsed as a dict.
    """
    fn = f"{self.cache_dir}/{key}.json"
    if not os.path.exists(fn):
      raise DuploExpiredCache(key)
    try:
      with open(fn, "r") as f:
        return json.load(f)
    except json.JSONDecodeError:
      raise DuploExpiredCache(key)
    
  def set_cached_item(self, key: str, data: dict) -> None:
    """Set Cached Item
    
    Set a cached item in the cache directory. The files are all json. 
    This writes the data to the file as a JSON object.

    Args:
      key: The key of the item to set.
      data: The data to set.
    """
    if not os.path.exists(self.cache_dir):
      os.makedirs(self.cache_dir)
    fn = f"{self.cache_dir}/{key}.json"
    with open(fn, "w") as f:
      json.dump(data, f)

  def interactive_token(self) -> str:
    """Interactive Token
    
    Performs an interactive login for the configured host. The cache will be checked for a token and if it is expired, it will perform an interactive login and cache the token. The cache may be disabled by setting the nocache flag. 
    
    Returns:
      The token as a string.
    """
    t = None
    k = self.cache_key_for("duplo-creds")
    try:
      if self.nocache:
        t = self.request_token()
      else:
        t = self.cached_token(k)
    except DuploExpiredCache:
      t = self.request_token()
      c = self.__token_cache(t)
      self.set_cached_item(k, c)
    return t
  
  def cached_token(self, key: str) -> str:
    """Cached Token
    
    Get a cached token from the cache directory. This checks if the file exists and raises a 404 if it does not. 
    Finally the file is read and returned as a JSON object. 
    The Expiration key looks like: "2024-01-12T18:51:48Z" in the popular iso8601 format.

    Args:
      host: The host to get the token for.

    Returns:
      The token as a string.
    """
    c = self.get_cached_item(key)
    if (exp := c.get("Expiration", None)) and (t := c.get("DuploToken", None)):
      if not self.expired(exp):
        return t
    raise DuploExpiredCache(key)
  
  def request_token(self) -> str:
    """Request Token from Browser
    
    Perform an interactive login to the specified host. Opens a temporary web browser to the login page and starts a local server to receive the token. When the user authorizes the request in the browser, the token is received and the server is shutdown.

    Returns:
      The token as a string.
    """
    isadmin = "true" if self.isadmin else "false"
    path = "app/user/verify-token"
    with TokenServer(self.host) as server:
      try:
        page = f"{path}?localAppName=duploctl&localPort={server.server_port}&isAdmin={isadmin}"
        server.open_callback(page, self.browser)
        return server.serve_token()
      except KeyboardInterrupt:
        server.shutdown()

  def cache_key_for(self, name: str) -> str:
    """Cache Key For
    
    Get the cache key for the given name. This is a simple string concatenation of the host and the name.

    Args:
      name: The name to get the cache key for.

    Returns:
      The cache key as a string.
    """
    h = self.host.split("://")[1].replace("/", "")
    parts = [h]
    if self.isadmin:
      parts.append("admin")
    parts.append(name)
    return ",".join(parts)
  
  def expiration(self, hours: int = 1) -> str:
    """Expiration
    
    Get the expiration time for the given number of hours. This is a simple calculation of the current time plus the number of hours.

    Args:
      hours: The number of seconds to add to the current time.

    Returns:
      The expiration time as a string.
    """

    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%S+00:00')
  
  def expired(self, exp: str = None) -> bool:
    """Expired
    
    Check if the given expiration time is expired. This is a simple comparison of the current time and the expiration time.

    Args:
      exp: The expiration time to check.

    Returns:
      True if the expiration time is in the past, False otherwise.
    """
    if exp is None:
      return True
    return datetime.now(timezone.utc) > datetime.fromisoformat(exp)
  
  def build_command(self, *args) -> list[str]:
    """Context Args
    
    Build a comamnd using the current context. 

    Returns:
      The context args as a dict.
    """
    cmd = list(args)
    # host is always needed
    cmd.append("--host")
    cmd.append(self.host)
    # tenant name or id or not at all
    if self.tenantid:
      cmd.append("--tenant-id")
      cmd.append(self.tenantid)
    elif self.tenant:
      cmd.append("--tenant")
      cmd.append(self.tenant)
    # only when admin
    if self.isadmin:
      cmd.append("--admin")
    # interactive settings or token
    if self.interactive:
      cmd.append("--interactive")
      if self.nocache:
        cmd.append("--nocache")
      if self.browser:
        cmd.append("--browser")
        cmd.append(self.browser)
    else:
      cmd.append("--token")
      cmd.append(self.token)
    return cmd
  
  def disable_get_cache(self) -> None:
    """Disable Get Cache
    
    Disable the get cache for this client. This is useful for testing.
    Disable by setting the __ttl_cache to None.
    """
    self.__ttl_cache = None

  def __token_cache(self, token, otp=False) -> dict:
    return {
      "Version": "v1",
      "DuploToken": token,
      "Expiration": self.expiration(),
      "NeedOTP": otp
    }
  
  def __headers(self) -> dict:
    t = self.token
    return {
      'Content-Type': 'application/json',
      'Authorization': f"Bearer {t}"
    }
  
  def __validate_response(self, response: requests.Response) -> requests.Response:
    """Validate a response from Duplo.
    
    Args:
      response: The response to validate.
    Raises:
      DuploError: If the response was not 200. 
    Returns:
      The response as a JSON object.
    """
    # contentType = response.headers.get('content-type', 'application/json').split(';')[0]
    if 200 <= response.status_code < 300:
      return response
    
    if response.status_code == 404:
      raise DuploError("Resource not found", response.status_code)
    
    if response.status_code == 401:
      raise DuploError(response.text, response.status_code)
    
    if response.status_code == 403:
      raise DuploError("Unauthorized", response.status_code)  
    
    if response.status_code == 400:
      raise DuploError(response.text, response.status_code)

    raise DuploError("Duplo responded with an error", response.status_code)
    
  def __sanitize_host(self, host: str) -> str:
    """Sanitize Host
    
    Sanitize the host using urlparse. This will ensure that the host is a valid URL and that it is using HTTPS.

    Args:
      host: The host to sanitize.
    Returns:
      The sanitized host with scheme.
    """
    if not host:
      return None
    url = urlparse(host)
    return f"https://{url.netloc}"
  
  
