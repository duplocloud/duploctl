import inspect 
import argparse
from importlib.metadata import entry_points
from .errors import DuploError
from . import args as t
from .types import Arg

ENTRYPOINT="duplocloud.net"
schema = {}

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
      if param.default is not inspect.Parameter.empty:
        param.annotation.default = param.default
      return param.annotation
    schema[function.__qualname__] = [
        arg_anno(k, v)
        for k, v in sig.parameters.items()
        if v.annotation is not inspect.Parameter.empty and isinstance(v.annotation, Arg)
    ]
    return function
  return decorator

def get_parser(qualname, known=False):
  parser = argparse.ArgumentParser(
    prog='duplocloud-cli',
    description='Duplo Cloud CLI',
  )
  try:
    for arg in schema[qualname]:
      parser.add_argument(*arg.flags, **arg.attributes)
  except KeyError:
    raise DuploError(f"Function named {qualname} not registered as a command.", 3)
  return parser

def load_service(name):
  """Load Service
    
  Load a Service class from the entry points.

  Args:
    name: The name of the service.
  Returns:
    The instantiated service with a reference to this client.
  """
  eps = entry_points()[ENTRYPOINT]
  # e = entry_points(group=group, name=kind)
  e = [ep for ep in eps if ep.name == name][0]
  svc = e.load()
  return svc
