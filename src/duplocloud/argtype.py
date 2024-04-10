from typing import NewType
import argparse
import yaml
import json 
from .errors import DuploError

class Arg(NewType):
  def __init__(self, 
              name, 
              *flags, 
              type=str, 
              action=None, 
              nargs=None, 
              const=None, 
              default=None, 
              choices=None, 
              required=None, 
              help=None, 
              metavar=None, 
              dest=None,
              version=None):
    """Command Argument Type

    Args:
      name (str): The name of the argument.
      type (type): The type of the argument.
      flag (str): The flag to use for the argument.
      action (str): The action to use for the argument.
      nargs (int): The number of arguments to use for the argument.
      const (str): The constant to use for the argument.
      default (str): The default value to use for the argument. This can be overriden by the default value of the arg in the function definition.
      choices (list): The choices to use for the argument.
      required (bool): Whether the argument is required.
      help (str): The help text to use for the argument.
      metavar (str): The metavar to use for the argument.
      dest (str): The destination to use for the argument.
      version (str): The version to use for the special version arg.
    """
    super().__init__(name, type)
    self.attributes = {}
    self._flags = flags
    # if action is not a string, then type is allowed
    if not isinstance(action, str):
      self.set_attribute("type", type)
    self.set_attribute("action", action)
    self.set_attribute("nargs", nargs)
    self.set_attribute("const", const)
    self.set_attribute("default", default)
    self.set_attribute("choices", choices)
    self.set_attribute("required", required)
    self.set_attribute("help", help)
    self.set_attribute("metavar", metavar)
    self.set_attribute("dest", dest)
    self.set_attribute("version", version)
  def set_attribute(self, key, value):
    if value is not None:
      self.attributes[key] = value
  @property
  def flags(self):
    if self.positional:
      # return the name
      return [self.__name__]
    return [*self._flags, f"--{self.__name__}"]
  @property
  def positional(self):
    return len(self._flags) == 0

class YamlAction(argparse.Action):
  def __init__(self, option_strings, dest, nargs=None, **kwargs):
    super().__init__(option_strings, dest, **kwargs)
  def __call__(self, parser, namespace, value, option_string=None):
    data = yaml.load(value, Loader=yaml.FullLoader)
    setattr(namespace, self.dest, data)

class JsonPatchAction(argparse._AppendAction):
  def __init__(self, option_strings, dest, nargs='+', metavar=('key', 'value'), **kwargs):
    opts = ["--add", "--remove", "--copy", "--replace", "--test", "--move"]
    super().__init__(opts, dest, nargs=nargs, metavar=metavar, **kwargs)
  def __call__(self, parser, namespace, value, option_string=None):
    def validate_key(key):
      key = key.replace(".", "/").replace("[", "/").replace("]", "")
      key = "/" + key if key[0] != "/" else key
      return key
    def validate_value(v):
      try:
        return json.loads(v)
      except json.JSONDecodeError:
        try: # attempt to load again with literal double quotes
          return json.loads('"' + v + '"')
        except json.JSONDecodeError: # still not so error
          raise DuploError(f"Invalid JSON value for {op} operation.")
    patch = None
    key = validate_key(value[0])
    op = option_string[2:]
    if op in ["add", "replace", "test"]:
      patch = {"op": op, "path": key, "value": validate_value(value[1])}
    elif op in ["remove"]:
      patch = {"op": op, "path": key}
    elif op in ["copy", "move"]:
      patch = {"op": op, "from": key, "path": validate_key(value[1])}
    super().__call__(parser, namespace, patch, option_string)
