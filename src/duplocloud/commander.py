import inspect 
import argparse
from importlib.metadata import entry_points
from .errors import DuploError

schema = {}

def DuploCommand():
  def decorator(function):
    # get the name of the function
    fx_args = inspect.signature(function)
    anno = function.__annotations__
    defaults = {
        k: v.default
        for k, v in fx_args.parameters.items()
        if v.default is not inspect.Parameter.empty
    }
    arguments = []
    for key, value in anno.items():
      if key in defaults:
        value.default = defaults[key]
      arguments.append(value)
    schema[function.__qualname__] = arguments
    return function
  return decorator

def exec(function, args=None):
  """Executes a function with the given arguments.
  
  Args:
    function: The function to execute.
    args: The arguments to pass to the function.
  Returns:
    The return value of the function.
  """
  parser = argparse.ArgumentParser(
    prog='duplocloud-cli',
    description='Duplo Cloud CLI',
  )
  try:
    for arg in schema[function.__qualname__]:
      parser.add_argument(*arg.flags, **arg.attributes)
  except KeyError:
    raise DuploError(f"Function named {function.__qualname__} not registered as a command.", 3)
  parsed_args = parser.parse_args(args)
  return function(**vars(parsed_args))
