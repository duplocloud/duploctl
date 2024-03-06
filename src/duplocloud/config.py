
import datetime
from pathlib import Path
import os
import yaml
import json
from .errors import DuploError, DuploExpiredCache
from .server import TokenServer
from . import args
from .commander import Command, get_parser

class DuploConfig():

  @Command()
  def __init__(self, 
               host: args.HOST=None, 
               token: args.TOKEN=None, 
               tenant: args.TENANT=None,
               home_dir: args.HOME_DIR = None, 
               config_file: args.CONFIG = None,
               cache_dir: args.CACHE_DIR = None,
               version: args.VERSION=False,
               interactive: args.INTERACTIVE=False,
               ctx: args.CONTEXT=None,
               nocache: args.NOCACHE=False,
               browser: args.BROWSER=None,
               isadmin: args.ISADMIN=False,
               query: args.QUERY=None,
               output: args.OUTPUT="json"):
    """DuploConfig
    
    An instance of a configuration for a certain duplo portal. This also includes any confiugration for the cache and the home directory so different portals can be used with different configurations.
    """
    
    # forces the given context to be used
    if ctx: 
      host = None
      token = None
    # ignore the given token with interactive mode
    if token and interactive: 
      token = None

    user_home = Path.home()
    self.home_dir = home_dir or f"{user_home}/.duplo"
    self.config_file = config_file or f"{self.home_dir}/config"
    self.cache_dir = cache_dir or f"{self.home_dir}/cache"
    self.__config = None
    self.__context = ctx
    self.__host = host.strip() if host else host
    self.__token = token.strip() if token else token
    self.__tenant = tenant.strip().lower() if tenant else tenant
    self.version = version
    self.interactive = interactive
    self.nocache = nocache
    self.browser = browser
    self.isadmin = isadmin
    self.query = query.strip() if query else query
    self.output = output.strip()

  @staticmethod
  def from_env():
    """DuploConfig from Environment

    Create a DuploConfig from environment variables.

    Returns:
      An instance of DuploConfig.
    """
    p = get_parser(DuploConfig.__init__)
    args, xtra = p.parse_known_args()
    c = DuploConfig(**vars(args))
    return c, xtra
  
  @property
  def settings(self):
    """Get Config

    Get the Duplo config as a dict. This is accessed as a lazy loaded property.

    Returns:
      The config as a dict.
    """
    if self.__config is None:
      if not os.path.exists(self.config_file):
        raise DuploError("Duplo config not found", 500)
      with open(self.config_file, "r") as f:
        self.__config = yaml.safe_load(f)
    return self.__config
  
  @property
  def context(self):
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
  def host(self):
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
  def token(self):
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
  def tenant(self):
    """Get Tenant
    
    Get the tenant from the Duplo config. This is accessed as a lazy loaded property. 
    If the tenant is some kind of falsey value, it will attempt to use the context.

    Returns:
      The tenant as a string.
    """
    if not self.host:
      raise DuploError("Host for Duplo portal is required", 500)
    return self.__tenant

  def use_context(self, name: str = None):
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
    self.__host = ctx.get("host", None)
    self.__token = ctx.get("token", None)
    self.__tenant = ctx.get("tenant", self.__tenant)
    self.interactive = ctx.get("interactive", False)
    self.isadmin = ctx.get("admin", False)
    self.nocache = ctx.get("nocache", False)
    # only tenant can be overridden by the args/env
    
  def get_cached_item(self, key: str):
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
    
  def set_cached_item(self, key: str, data: dict):
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

  def interactive_token(self):
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
  
  def cached_token(self, key: str):
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
  
  def request_token(self):
    """Request Token from Browser
    
    Perform an interactive login to the specified host. Opens a temporary web browser to the login page and starts a local server to receive the token. When the user authorizes the request in the browser, the token is received and the server is shutdown.

    Args:
      host: The host to login to.

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

  def cache_key_for(self, name: str):
    """Cache Key For
    
    Get the cache key for the given name. This is a simple string concatenation of the host and the name.

    Args:
      name: The name to get the cache key for.

    Returns:
      The cache key as a string.
    """
    h = self.host.split("://")[1]
    parts = [h]
    if self.isadmin:
      parts.append("admin")
    parts.append(name)
    return ",".join(parts)
  
  def expiration(self, hours: int = 6):
    """Expiration
    
    Get the expiration time for the given number of hours. This is a simple calculation of the current time plus the number of hours.

    Args:
      hours: The number of seconds to add to the current time.

    Returns:
      The expiration time as a string.
    """
    return (datetime.datetime.now() + datetime.timedelta(hours=hours)).isoformat()
  
  def expired(self, exp: str = None):
    """Expired
    
    Check if the given expiration time is expired. This is a simple comparison of the current time and the expiration time.

    Args:
      exp: The expiration time to check.

    Returns:
      True if the expiration time is in the past, False otherwise.
    """
    if exp is None:
      return True
    return datetime.datetime.now() > datetime.datetime.fromisoformat(exp)

  def __token_cache(self, token, otp=False):
    return {
      "Version": "v1",
      "DuploToken": token,
      "Expiration": self.expiration(),
      "NeedOTP": otp
    }
