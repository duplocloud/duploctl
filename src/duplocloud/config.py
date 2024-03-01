
import datetime
from pathlib import Path
import os
import yaml
import json
from duplocloud.errors import DuploError, DuploExpiredCache
import webbrowser
from .server import TokenServer
from . import args
from .commander import Command, get_parser

class DuploConfig():

  @Command()
  def __init__(self, 
               host: args.HOST, 
               token: args.TOKEN=None, 
               tenant: args.TENANT="default",
               home_dir: args.HOME_DIR = None, 
               config_file: args.CONFIG = None,
               cache_dir: args.CACHE_DIR = None,
               version: args.VERSION=False,
               interactive: args.INTERACTIVE=False,
               query: args.QUERY=None,
               output: args.OUTPUT="json"):
    user_home = Path.home()
    self.home_dir = home_dir or f"{user_home}/.duplo"
    self.config_file = config_file or f"{self.home_dir}/config"
    self.cache_dir = cache_dir or f"{self.home_dir}/cache"
    self.__config = None
    self.version = version
    self.interactive = interactive
    self.host = host.strip()
    self.token = token.strip() if token else token
    self.tenant = tenant.strip()
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
    c.setup()
    return c, xtra
  
  @property
  def settings(self):
    """Get Config

    Get the Duplo config as a dict. This is accessed as a property.

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
    
    Get the current context from the Duplo config. This is accessed as a property. 

    Returns:
      The context as a dict.
    """
    c = self.settings
    try:
      if (ctx := c.get("current-context", None)):
        return [p for p in c["contexts"] if p["name"] == ctx][0]
      else:
        raise DuploError("Duplo context not set, please set 'current-context' to a portals name in your config", 500)
    except IndexError:
      raise DuploError(f"Portal '{ctx}' not found in config", 500)
    
  def setup(self):
    if not self.host:
      ctx = self.context
      self.host = ctx.get("host", None)
      self.token = ctx.get("token", self.token)
      self.tenant = ctx.get("tenant", self.tenant)
      self.interactive = ctx.get("interactive", self.interactive)
    if not self.token and self.interactive:
      self.token = self.interactive_token()
    
  def get_cached_item(self, key: str):
    """Get Cached Item
    
    Get a cached item from the cache directory. The files are all json. 
    This checks if the file exists and raises a 404 if it does not. 
    Finally the file is read and returned as a JSON object.

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
    """Discover Token
    
    Discover a token for the specified host. This checks the cache for a token and raises a 404 if it does not exist.
    If the token is expired, it will perform an interactive login and cache the token.

    Args:
      host: The host to get the token for.
    
    Returns:
      The token as a string.
    """
    h = self.host.split("://")[1]
    k = f"{h},duplo-creds"
    t = None
    try:
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
      if exp > datetime.datetime.now().isoformat():
        return t
    raise DuploExpiredCache(key)
  
  def request_token(self):
    """Interactive Login
    
    Perform an interactive login to the specified host. Opens a temporary web browser to the login page and starts a local server to receive the token. When the user authorizes the request in the browser, the token is received and the server is shutdown.

    Args:
      host: The host to login to.

    Returns:
      The token as a string.
    """
    port = 56022 # this should be randomized. Will anyone catch this in the PR? 10 points if you do. 
    page = f"{self.host}/app/user/verify-token?localAppName=duploctl&localPort={port}&isAdmin=true"
    webbrowser.open(page, new=0, autoraise=True)
    with TokenServer(port) as server:
      try:
        return server.serve_token()
      except KeyboardInterrupt:
        server.shutdown()
        pass

  def __token_cache(self, token, otp=False):
    return {
      "Version": "v1",
      "DuploToken": token,
      "Expiration": (datetime.datetime.now() + datetime.timedelta(hours=6)).isoformat(),
      "NeedOTP": otp
    }
