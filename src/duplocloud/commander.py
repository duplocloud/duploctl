import inspect 
import argparse
from copy import deepcopy
from importlib.metadata import entry_points
from .errors import DuploError
from .argtype import Arg


ENTRYPOINT="duplocloud.net"
FORMATS=f"formats.{ENTRYPOINT}"
ep = entry_points(group=ENTRYPOINT)
fep = entry_points(group=FORMATS)
schema = {}
resources = {}

def Resource(name: str):
  def decorator(cls):
    resources[name] = {
      "class": cls.__qualname__
    }
    return cls
  return decorator

def Command():
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
    sig = inspect.signature(function)
    def arg_anno(name, param):
      a = deepcopy(param.annotation)
      if not a.positional and name != a.__name__:
        a.set_attribute("dest", name)
      if param.default is not inspect.Parameter.empty:
        a.set_attribute("default", param.default)
      return a
    schema[function.__qualname__] = [
        arg_anno(k, v)
        for k, v in sig.parameters.items()
        if v.annotation is not inspect.Parameter.empty and isinstance(v.annotation, Arg)
    ]
    return function
  return decorator

def get_parser(function):
  """Get Parser
  
  Args:
    function: The function to get the parser for.
  Returns:
    An argparse.ArgumentParser object with args from function.
  """
  qn = function.__qualname__
  parser = argparse.ArgumentParser(
    prog='duplocloud-client',
    description='Duplo Cloud CLI',
  )
  try:
    for arg in schema[qn]:
      parser.add_argument(*arg.flags, **arg.attributes)
  except KeyError:
    raise DuploError(f"Function named {qn} not registered as a command.", 3)
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

