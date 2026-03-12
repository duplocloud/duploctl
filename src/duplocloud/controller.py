
import sys
import jmespath
import os
import yaml
import jsonpatch
import logging
import traceback
from urllib.parse import urlparse
from pathlib import Path
from .commander import load_resource, load_format, load_client
from .errors import DuploError, DuploInvalidError
from . import args
from .commander import Command, get_parser, extract_args, available_resources, VERSION
from typing import TypeVar
try:
  import duplocloud_sdk
  from pydantic import ValidationError
except ImportError:
  duplocloud_sdk = None
  ValidationError = None

T = TypeVar("T")

class DuploCtl():
  """Duplo Ctl

  This is the main IoC container for the Duplo CLI. It manages configuration,
  resources, clients, formatters, and models. HTTP and auth behavior live in
  pluggable client classes loaded via the client extension point system.

  Example: Using injected client to load a service.
      ```python
      from duplocloud.controller import DuploCtl
      from duplocloud.resource import DuploResource
      from duplocloud.errors import DuploError

      class DuploSomeService(DuploResource):
        def __init__(self, duplo: DuploCtl):
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
               wait: args.WAIT=False,
               wait_timeout: args.WAIT_TIMEOUT=None,
               validate: args.VALIDATE=False):
    """DuploCtl Constructor

    Creates an instance of a duplocloud client configured for a certain portal. All of the arguments are optional and can be set in the environment or in the config file. The types of each of the arguments are annotated types that are used by argparse to create the command line arguments.

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
      duplo (DuploCtl): An instance of a DuploCtl.
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
    self._config = None
    self._context = ctx
    self._host = self._sanitize_host(host)
    self._token = token.strip() if token else token
    self._tenant = tenant.strip().lower() if tenant else tenant
    self.tenantid = tenant_id.strip() if tenant_id else tenant_id
    self.version = version
    self.interactive = interactive
    self.nocache = nocache
    self.browser = browser
    self.isadmin = isadmin
    self.query = query.strip() if query else query
    self.output = output.strip()
    self.timeout = 60
    self.loglevel = loglevel
    self.logger = self.logger_for()
    self.wait = wait
    self.wait_timeout = wait_timeout
    self.validate = validate
    self._clients = {}

  @staticmethod
  def from_env():
    """From Environment

    Create a DuploCtl from environment variables. This is the most common way to create a DuploCtl.

    Usage: New Client From Environment
      ```python
      duplo, args = DuploCtl.from_env()
      ```

    Returns:
      duplo (DuploCtl): An instance of a DuploCtl.
    """
    a = extract_args(DuploCtl.__init__)
    p = get_parser(a)
    env, xtra = p.parse_known_args()
    duplo = DuploCtl(**vars(env))
    return duplo, xtra

  @staticmethod
  def from_args(*args: str):
    """DuploCtl from Arguments

    Create a DuploCtl from an array of global client arguments.

    Args:
      args: An array of global client arguments aligning with the DuploCtl constructor.

    Returns:
      duplo (DuploCtl): An instance of DuploCtl.
    """
    a = extract_args(DuploCtl.__init__)
    p = get_parser(a)
    env = p.parse_args(args)
    duplo = DuploCtl(**vars(env))
    return duplo

  @staticmethod
  def from_creds(host: str, token: str, tenant: str):
    """Create a DuploCtl from credentials.

    Args:
      host: The host of the Duplo instance.
      token: The token to use for authentication.
      tenant: The tenant to use.

    Returns:
      duplo (DuploCtl): The DuploCtl.
    """
    return DuploCtl(host=host, token=token, tenant=tenant)

  @property
  def token(self) -> str:
    """Token

    Returns the configured token value from args/env/context. May be None.
    """
    return self._token

  @token.setter
  def token(self, value: str) -> None:
    """Set Token"""
    self._token = value

  @property
  def settings(self) -> dict:
    """Get Config

    Get the Duplo config as a dict. This is accessed as a lazy loaded property.

    Returns:
      settings: The config as a dict.
    """
    if self._config is None:
      if not os.path.exists(self.config_file):
        raise DuploError("Duplo config not found", 500)
      with open(self.config_file, "r") as f:
        self._config = yaml.safe_load(f)
    return self._config

  @property
  def context(self) -> dict:
    """Get Config Context

    Get the current context from the Duplo config. This is accessed as a lazy loaded property.

    Returns:
      The context as a dict.
    """
    s = self.settings
    ctx = self._context if self._context else s.get("current-context", None)
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
    if not self._host:
      self.use_context()
    return self._host

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
    return self._tenant

  @tenant.setter
  def tenant(self, value: str) -> None:
    """Set Tenant

    Set the tenant for this Duplo client. This will override the tenant in the config.

    Args:
      value: The tenant to set.
    """
    self._tenant = value

  @property
  def config(self) -> dict:
    return {
      "Host": self.host,
      "Tenant": self.tenant or self.tenantid,
      "HomeDir": self.home_dir,
      "ConfigFile": self.config_file,
      "CacheDir": self.cache_dir,
      "Version": VERSION,
      "Path": sys.argv[0],
      "AvailableResources": available_resources()
    }

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

  def __call__(self, resource: str=None, *args, query: str=None, **kwargs):
    """Run a service command.

    Choose a resource name and pass it's params in. Each resource has a unique set of arguments and therefore there is no need to try and define anything beyond a resource name and an optional query. Everything else is processed by the resource itself in it's own call method. Not all resources have commands and only execute their call method.

    Args:
      resource: The name of the resource.
      args: The arguments to the resource.
      query: Optional JMESPath query override for this invocation.
      kwargs: Additional keyword arguments passed to the command.
    Returns:
      The result of the command.
    """
    d = None
    if not resource:
      d = self.config
    else:
      r = self.load(resource)
      try:
        d = r(*args, **kwargs)
      except TypeError as te:
        self.logger.debug(te)
        if (r.__doc__):
          raise DuploError(r.__doc__, 400)
        else:
          traceback.print_exc()
          raise DuploError(f"No docstring found, error calling command {resource} : Traceback printed", 400)
    if d is None:
      return None
    d = self.filter(d, query=query)
    return self.format(d)
  
  def use_context(self, name: str = None) -> None:
    """Use Context

    Use the specified context from the Duplo config.

    Args:
      name: The name of the context to use.
    """

    # Get the right context
    if name:
      self._context = name
    ctx = self.context

    # set the context into this config
    self._host = self._sanitize_host(ctx.get("host", None))
    self._token = ctx.get("token", None)
    self._tenant = ctx.get("tenant", self._tenant)
    self.interactive = ctx.get("interactive", False)
    self.isadmin = ctx.get("admin", False)
    self.nocache = ctx.get("nocache", False)

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

  def filter(self, data, query: str=None):
    """Query data

    Uses the jmespath library to query data.
    An explicit query override can be passed per invocation,
    otherwise falls back to the global self.query property.

    Args:
      data: The data to query.
      query: Optional JMESPath query override.
    Returns:
      The queried data.
    """
    q = query or self.query
    if not q:
      return data
    try:
      return jmespath.search(q, data)
    except jmespath.exceptions.ParseError as e:
      raise DuploError("Invalid JMESPath query - parsing failed", 500) from e
    except jmespath.exceptions.JMESPathTypeError as e:
      raise DuploError("Invalid JMESPath query - data type mismatch", 500) from e
    
  def load_client(self, name: str = "duplo"):
    """Load Client

    Load and cache a client singleton via the client extension point system.

    Args:
      name: The name of the client.

    Returns:
      The client instance.
    """
    if name not in self._clients:
      cls = load_client(name)
      self._clients[name] = cls(self)
    return self._clients[name]

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

  def load_model(self, model_name: str):
    """Load Model

    Load a Pydantic model class by name from the duplocloud_sdk.
    Returns None if the model is not found.

    Args:
      model_name: The name of the Pydantic model class (e.g. "AddTenantRequest").

    Returns:
      The Pydantic model class, or None if not found.
    """
    if not model_name:
      return None
    if duplocloud_sdk is None:
      raise DuploError(
        "--validate requires duplocloud-sdk: "
        "pip install duplocloud-sdk", 1
      )
    return getattr(duplocloud_sdk, model_name, None)

  def validate_model(self, model, data: dict) -> dict:
    """Validate Model

    Validate data against a Pydantic model class.
    Takes the model class directly (not a name string).
    Does not check the global validate flag — callers decide when to call this.
    Raises DuploInvalidError if validation fails.

    Args:
      model: The Pydantic model class.
      data: The dict to validate.

    Returns:
      The validated and serialized dict.

    Raises:
      DuploInvalidError: If the data fails model validation.
    """
    try:
      instance = model.model_validate(data)
      return instance.model_dump(by_alias=True, exclude_none=True)
    except ValidationError as e:
      raise DuploInvalidError(str(e)) from e

  def load_formatter(self, name: str="string"):
    """Load Formatter

    Load a Formatter function from the entry points.

    Args:
      name: The name of the format.
    Returns:
      The class of the format.
    """
    return load_format(name)

  def format(self, data, output: str=None):
    """Format data.

    Args:
      data: The data to format.
      output: The output format to use. Defaults to self.output.
    Returns:
      The formatted data as a string, or the raw data when output is None.
    """
    o = output or self.output
    if o is None:
      return data
    fmt = self.load_formatter(o)
    return fmt(data)

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
    elif self._token:
      cmd.append("--token")
      cmd.append(self._token)
    return cmd

  def _sanitize_host(self, host: str) -> str:
    """Sanitize Host

    Sanitize the host using urlparse. This will ensure that the host is a valid URL and that it is using HTTPS.
    Handles hosts with or without scheme (http/https).

    Args:
      host: The host to sanitize.
    Returns:
      The sanitized host with https scheme.
    """
    if not host:
      return None

    # Check if the host has a scheme
    if not host.startswith('http://') and not host.startswith('https://'):
      # If no scheme, prepend https:// temporarily to make urlparse work correctly
      host = f"https://{host}"

    url = urlparse(host)
    return f"https://{url.netloc}"

DuploClient = DuploCtl
