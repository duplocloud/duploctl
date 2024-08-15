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

def Resource(name: str):
  def decorator(cls):
    resources[name] = {
      "class": cls.__qualname__
    }
    setattr(cls, "kind", name)
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
  
  Given a name of a command, check the schema and find the real method name because the command might be aliased.
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
