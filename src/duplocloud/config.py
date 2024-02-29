
import datetime
from pathlib import Path
import os
import yaml
import json
from duplocloud.errors import DuploError, DuploExpiredCache
import webbrowser
from .server import TokenServer

class DuploConfig():

  def __init__(self, 
               home_dir: str = None, 
               config_file: str = None,
               cache_dir: str = None):
    user_home = Path.home()
    self.home_dir = home_dir or f"{user_home}/.duplo"
    self.config_file = config_file or f"{self.home_dir}/config"
    self.cache_dir = cache_dir or f"{self.home_dir}/cache"
    self.__config = None

  @staticmethod
  def from_env():
    """DuploConfig from Environment

    Create a DuploConfig from environment variables.

    Returns:
      An instance of DuploConfig.
    """
    home_dir = os.getenv("DUPLO_HOME", None)
    config_file = os.getenv("DUPLO_CONFIG", None)
    cache_dir = os.getenv("DUPLO_CACHE", None)
    return DuploConfig(home_dir, config_file, cache_dir)
  
  @property
  def config(self):
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
    c = self.config
    try:
      if (ctx := c.get("current-context", None)):
        return [p for p in c["contexts"] if p["name"] == ctx][0]
      else:
        raise DuploError("Duplo context not set, please set 'current-context' to a portals name in your config", 500)
    except IndexError:
      raise DuploError(f"Portal '{ctx}' not found in config", 500)
    
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

  def discover_token(self, host: str):
    """Discover Token
    
    Discover a token for the specified host. This checks the cache for a token and raises a 404 if it does not exist.
    If the token is expired, it will perform an interactive login and cache the token.

    Args:
      host: The host to get the token for.
    
    Returns:
      The token as a string.
    """
    h = host.split("://")[1]
    k = f"{h},duplo-creds"
    t = None
    try:
      t = self.cached_token(k)
    except DuploExpiredCache:
      t = self.interactive_token(host)
      c = self.__duplo_token_cache(t)
      self.set_cached_item(k, c)
    return t
  
  def cached_token(self, k: str):
    """Cached Token
    
    Get a cached token from the cache directory. This checks if the file exists and raises a 404 if it does not. 
    Finally the file is read and returned as a JSON object. 
    The Expiration key looks like: "2024-01-12T18:51:48Z" in the popular iso8601 format.

    Args:
      host: The host to get the token for.

    Returns:
      The token as a string.
    """
    c = self.get_cached_item(k)
    if (exp := c.get("Expiration", None)) and (t := c.get("DuploToken", None)):
      if exp > datetime.datetime.now().isoformat():
        return t
    raise DuploExpiredCache(k)
    
  
  def interactive_token(self, host: str):
    """Interactive Login
    
    Perform an interactive login to the specified host.

    Args:
      host: The host to login to.
    """
    port = 56022
    page = f"{host}/app/user/verify-token?localAppName=duploctl&localPort={port}&isAdmin=true"
    webbrowser.open(page, new=0, autoraise=True)
    with TokenServer(port, 20) as server:
      try:
        return server.token_server()
      except KeyboardInterrupt:
        server.shutdown()
        pass

  def __duplo_token_cache(self, token, otp=False):
    return {
      "Version": "v1",
      "DuploToken": token,
      "Expiration": (datetime.datetime.now() + datetime.timedelta(hours=6)).isoformat(),
      "NeedOTP": otp
    }
