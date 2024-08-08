import inspect 
import argparse
from copy import deepcopy
from importlib.metadata import entry_points, version
from .errors import DuploError
from .argtype import Arg


ENTRYPOINT="duplocloud.net"
FORMATS=f"formats.{ENTRYPOINT}"
VERSION=version('duplocloud-client')
ep = entry_points(group=ENTRYPOINT)
fep = entry_points(group=FORMATS)
schema = {}
resources = {}

def Resource(name: str):
  def decorator(cls):
    resources[name] = {
      "class": cls.__qualname__
    }
    setattr(cls, "kind", name)
    return cls
  return decorator

def Command(*aliases):
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
    The decorated function.

  """
  def decorator(function):
    schema[function.__qualname__] = {
      "method": function.__name__,
      "aliases": list(aliases),
    }
    return function
  return decorator

def extract_args(function):
  sig = inspect.signature(function)
  def arg_anno(name, param):
    a = deepcopy(param.annotation)
    if not a.positional and name != a.__name__:
      a.set_attribute("dest", name)
    # hmmm, is this a good idea? If so, maybe some innovations is needed. 
    # if param.default is not inspect.Parameter.empty:
    #   a.set_attribute("default", param.default)
    return a
  return [
    arg_anno(k, v)
    for k, v in sig.parameters.items()
    if v.annotation is not inspect.Parameter.empty and isinstance(v.annotation, Arg)
  ]

def aliased_method(classname: str, command: str):
  """Schema For
  
  Get the schema for a function.

  Args:
    name: The name of the function.
  Returns:
    The schema for the function.
  """
  s = next((
    v for k, v in schema.items()
    if k.startswith(classname) and (command == v["method"] or command in v.get("aliases", []))
  ), None)
  if not s:
    raise DuploError(f"Command {command} not found.", 404)
  return s["method"]

def get_parser(args: list):
  """Get Parser
  
  Args:
    function: The function to get the parser for.
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

def available_resources():
  """Available Resources

  Returns:
    A list of available resources names.
  """
  return list(ep.names)

def available_formats():
  """Available Formats

  Returns:
    A list of available format names.
  """
  return list(fep.names)
