import argparse
from copy import deepcopy
from importlib.metadata import entry_points, version
from inspect import signature, getmro, Parameter
from .errors import DuploError
from .argtype import Arg
from typing import Callable, List, Type

ENTRYPOINT="duplocloud.net"
FORMATS=f"formats.{ENTRYPOINT}"
VERSION=version('duplocloud-client')
ep = entry_points(group=ENTRYPOINT)
fep = entry_points(group=FORMATS)
schema = {}
resources = {}

def _inject_tenant_scope(cls):
  """Inject tenant-scoped functionality into a resource class.
  
  This adds properties and methods needed for tenant-scoped resources without
  requiring deep inheritance hierarchies.
  
  Args:
    cls: The class to inject tenant functionality into.
    
  Returns:
    cls: The modified class with tenant functionality.
  """
  # Add private attributes initialization
  original_init = cls.__init__
  
  def new_init(self, duplo, *args, **kwargs):
    original_init(self, duplo, *args, **kwargs)
    self._tenant = None
    self._tenant_id = None
    self.tenant_svc = duplo.load('tenant')
  
  setattr(cls, '__init__', new_init)
  
  # Add tenant property
  @property
  def tenant(self):
    if not self._tenant:
      self._tenant = self.tenant_svc.find()
      self._tenant_id = self._tenant["TenantId"]
    return self._tenant
  
  setattr(cls, 'tenant', tenant)
  
  # Add tenant_id property
  @property
  def tenant_id(self):
    if not self._tenant_id:
      if self._tenant:
        self._tenant_id = self._tenant["TenantId"]
      elif self.duplo.tenantid:
        self._tenant_id = self.duplo.tenantid
      else:
        self._tenant_id = self.tenant["TenantId"]
    return self._tenant_id
  
  setattr(cls, 'tenant_id', tenant_id)
  
  # Add prefix property (uses dynamic ResourceNamePrefix from system info)
  @property
  def prefix(self):
    if not hasattr(self, '_prefix') or self._prefix is None:
      sys_svc = self.duplo.load("system")
      info = sys_svc.info()
      resource_prefix = info.get("ResourceNamePrefix", "duploservices")
      self._prefix = f"{resource_prefix}-{self.tenant['AccountName']}-"
    return self._prefix
  
  setattr(cls, 'prefix', prefix)
  
  # Add prefixed_name method
  def prefixed_name(self, name: str) -> str:
    if not name.startswith(self.prefix):
      name = f"{self.prefix}{name}"
    return name
  
  setattr(cls, 'prefixed_name', prefixed_name)
  
  # Override endpoint method with tenant-scoped version
  def endpoint(self, name_or_path: str=None, path: str=None):
    """Tenant-scoped endpoint builder.
    
    For V2 resources: endpoint(path) -> f"subscriptions/{tenant_id}/{path}"
    For V3 resources: endpoint(name, path) -> f"v3/subscriptions/{tenant_id}/{slug}/{name}/{path}"
    """
    if self.api_version == "v3":
      # V3 behavior: endpoint(name, path)
      p = f"v3/subscriptions/{self.tenant_id}/{self.slug}"
      if name_or_path:  # This is 'name' for V3
        p += f"/{name_or_path}"
      if path:
        p += f"/{path}"
      return p
    else:
      # V2 behavior: endpoint(path)
      path = name_or_path  # For V2, first param is the path
      return f"subscriptions/{self.tenant_id}/{path}"
  
  setattr(cls, 'endpoint', endpoint)
  
  return cls

def Resource(name: str, scope: str = "portal"):
  """Resource decorator
  
  Registers a class as a resource and optionally injects scope-specific functionality.
  
  Args:
    name: The name of the resource.
    scope: The scope of the resource. Valid values are "portal" or "tenant". Defaults to "portal".
    
  Returns:
    decorator: The decorator function.
    
  Raises:
    ValueError: If an invalid scope is provided.
  """
  if scope not in ("portal", "tenant"):
    raise ValueError(f"Invalid scope '{scope}'. Must be 'portal' or 'tenant'.")
  
  def decorator(cls):
    resources[name] = {
      "class": cls.__qualname__,
      "parent": cls.__bases__[0].__name__ if cls.__bases__ and cls.__bases__[0].__name__ != "object" else None,
      "scope": scope
    }
    setattr(cls, "kind", name)
    setattr(cls, "scope", scope)
    
    # Inject tenant functionality if tenant-scoped
    if scope == "tenant":
      cls = _inject_tenant_scope(cls)
    
    return cls
  return decorator

def Command(*aliases) -> Callable:
  """Command decorator

  This decorator is used to register a function as a command. It will
  automatically generate the command line arguments for the function
  based on the annotations.

  Example:
    ```python
    from duplocloud.commander import Command
    from duplocloud import args
    @Command()
    def hello(name: args.NAME = "world"):
      print(f"Hello {name}!")
    ```
  
  Returns:
    decorator: The decorated function.

  """
  def decorator(function: Callable):
    schema[function.__qualname__] = {
      "class": function.__qualname__.split(".")[0],
      "method": function.__name__,
      "aliases": list(aliases),
    }
    return function
  return decorator

def extract_args(function: Callable) -> List[Arg]:
  """Extract Args
  
  Extract the cli argument annotations from a function. This will only collect the args of type duplocloud.Arg. 
  This list can now be used to generate an argparse.ArgumentParser object.
  
  """
  sig = signature(function)
  def arg_anno(name, param):
    a = deepcopy(param.annotation)
    if not a.positional and name != a.__name__:
      a.set_attribute("dest", name)
    # hmmm, is this a good idea? If so, maybe some innovations is needed. 
    # if param.default is not Parameter.empty:
    #   a.set_attribute("default", param.default)
    return a
  return [
    arg_anno(k, v)
    for k, v in sig.parameters.items()
    if v.annotation is not Parameter.empty and isinstance(v.annotation, Arg)
  ]

def aliased_method(cls: Type, command: str) -> str:
  """Aliased Method
  
  Given the name of a command, check the schema and find the real method name because the command might be aliased.
  The given class will be used to discover any ancestors because the command may actually come from a parent class.

  Args:
    cls: The class to check the schema for.
    command: The command to find the

  Returns:
    method: The true name of the commands method.
  """
  clss = [c.__name__ for c in getmro(cls) if c.__name__ != "object"]
  s = next((
    v for v in schema.values()
    if (v["class"] in clss) and (command == v["method"] or command in v.get("aliases", []))
  ), None)
  if not s:
    raise DuploError(f"Command {command} not found.", 404)
  return s["method"]

def get_parser(args: List[Arg]) -> argparse.ArgumentParser:
  """Get Parser
  
  Args:
    args: A list of Arg objects.
  Returns:
    An argparse.ArgumentParser object with args from function.
  """
  parser = argparse.ArgumentParser(
    prog='duplocloud-client',
    description='Duplo Cloud CLI',
  )
  for arg in args:
    parser.add_argument(*arg.flags, default=arg.default, **arg.attributes)
  return parser

def load_resource(name: str):
  """Load Service
    
  Load a Service class from the entry points.

  Args:
    name: The name of the service.
  Returns:
    The class of the service.
  """
  try:
    return ep[name].load()
  except KeyError:
    avail = available_resources()
    raise DuploError(f"""
Resource named {name} not found.
Available resources are:
  {", ".join(avail)}
""", 404)

def load_format(name: str="string"):
  """Load Format
    
  Load a Formatter function from the entry points.

  Args:
    name: The name of the format.
  Returns:
    The class of the format.
  """
  return fep[name].load()

def available_resources() -> List[str]:
  """Available Resources

  Returns:
    A list of available resources names.
  """
  return list(ep.names)

def available_formats() -> List[str]:
  """Available Formats

  Returns:
    A list of available format names.
  """
  return list(fep.names)

def commands_for(name: str) -> dict:
  """Commands For

  Get all command methods decorated with @Command for a given resource.
  
  This function builds a dictionary of all available commands for a resource,
  including inherited commands from parent classes. Parent class commands are added
  first to simulate class extension, then the resource's own commands are added,
  allowing child classes to override parent methods.

  The schema is built from the global `schema` dict which tracks all @Command decorated
  methods, and the `resources` dict which tracks class inheritance relationships.

  Args:
    name: The name of the resource (e.g., "tenant", "service").
    
  Returns:
    A dict where keys are method names and values are command metadata dicts containing:
      - class: The class name where the method is defined
      - method: The method name
      - aliases: List of alternative command names
      
  Example:
    ```python
    commands_for("tenant")
    # Returns: {"find": {"class": "DuploTenant", "method": "find", "aliases": []}}
    ```
  """
  if name not in resources:
    raise DuploError(f"Resource named {name} not found.", 404)
  
  resource = resources[name]
  result = {}
  
  # First, add parent class methods if parent exists
  if resource["parent"]:
    parent_class = resource["parent"]
    for method_schema in schema.values():
      if method_schema["class"] == parent_class:
        result[method_schema["method"]] = method_schema
  
  # Then, add or override with the resource's own methods
  resource_class = resource["class"]
  for method_schema in schema.values():
    if method_schema["class"] == resource_class:
      result[method_schema["method"]] = method_schema
  
  return result
