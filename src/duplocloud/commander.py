import inspect 
import argparse
from importlib.metadata import entry_points
from .errors import DuploError
from . import args as t

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
    arguments = []
    fx_args = inspect.signature(function)
    anno = function.__annotations__
    defaults = {
        k: v.default
        for k, v in fx_args.parameters.items()
        if v.default is not inspect.Parameter.empty
    }
    for key, value in anno.items():
      if key in defaults:
        value.default = defaults[key]
      arguments.append(value)
    schema[function.__qualname__] = arguments
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

def load_env():
  """Get the environment variables for the Duplo session.
  
  Returns:
    A tuple containing the enviorment variables and the remaining arguments for a command. 
  """
  parser = argparse.ArgumentParser(
    prog='duplocloud-cli',
    description='Duplo Cloud CLI',
  )
  parser.add_argument(*t.SERVICE.flags, **t.SERVICE.attributes)
  parser.add_argument(*t.COMMAND.flags, **t.COMMAND.attributes)
  parser.add_argument(*t.TENANT.flags, **t.TENANT.attributes)
  parser.add_argument(*t.HOST.flags, **t.HOST.attributes)
  parser.add_argument(*t.TOKEN.flags, **t.TOKEN.attributes)
  return parser.parse_known_args()

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
