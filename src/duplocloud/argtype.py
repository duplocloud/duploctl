"""
This module contains the customizations to the Argparse library. 
"""
from typing import NewType, Any, List
import argparse
import yaml
import json 
import os
from .errors import DuploError

class Arg(NewType):
  """Duplo ArgType
  
  A custom type for defining arguments in Duplo commands as annotations. 
  This extends the NewType class so type hinting will work as expected and we get truly new types. 
  Each instance of this class will be used to define a command line argument for a function.
  The values contained are the values needed for the argparse.ArgumentParser.add_argument method.

  Example:
    Make a reusable arg type called `foo`
    ```python
    FOO = Arg("foo", "-f", help="A foo arg")
    ```
  """
  def __init__(self, 
              name: str, 
              *flags: List[str], 
              type: Any=str, 
              action: str=None, 
              nargs: str=None, 
              const: str=None, 
              default=None, 
              choices=None, 
              required: bool=None, 
              help: str=None, 
              metavar: tuple=None, 
              dest: str=None,
              version: bool=None,
              env: str=None):
    """Initialize ArgType

    Args:
      name: The name of the argument.
      type: The type of the argument.
      flags: The flag to use for the argument.
      action: The action to use for the argument.
      nargs: The number of arguments to use for the argument.
      const: The constant to use for the argument.
      default (any): The default value to use for the argument. This can be overriden by the default value of the arg in the function definition.
      choices (List[any]): The choices to use for the argument.
      required: Whether the argument is required.
      help: The help text to use for the argument.
      metavar: The metavar to use for the argument.
      dest: The destination to use for the argument.
      version: The version to use for the special version arg.
      env: The environment variable to use for the argument.
    """
    super().__init__(name, type)
    self.attributes = {}
    self.env = env
    self.__flags = flags
    self.__default = default
    # if action is not a string, then type is allowed
    if not isinstance(action, str):
      self.set_attribute("type", type)
    self.set_attribute("action", action)
    self.set_attribute("nargs", nargs)
    self.set_attribute("const", const)
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
    return [f"--{self.__name__}", *self.__flags]
  @property
  def positional(self):
    return len(self.__flags) == 0
  
  @property
  def default(self):
    if self.env:
      return os.getenv(self.env, self.__default)
    else:
      return self.__default
  
  @property 
  def type_name(self):
    # t = self.attributes.get("type", self.__supertype__)
    t = self.__supertype__
    return getattr(t, "__name__", str(t))
  
  def __str__(self):
    return self.attributes.get("help", "")

class YamlAction(argparse.Action):
  """Yaml Action
  
  A custom action for argparse that loads a yaml file into a python object. 
  This is intended to be used alongside the File type in argparse. This way
  the file type (yaml) is enforced. 
  """
  def __init__(self, option_strings, dest, nargs=None, **kwargs):
    super().__init__(option_strings, dest, **kwargs)
  def __call__(self, parser, namespace, value, option_string=None):
    data = yaml.load(value, Loader=yaml.FullLoader)
    setattr(namespace, self.dest, data)

class JsonPatchAction(argparse._AppendAction):
  """Json Patch Action

  A custom argparse action that translates [JSON Patch](https://jsonpatch.com/) operations from the command line arguments. This allows users to specify operations like `add`, `remove`, `copy`, `replace`, `test`, and `move` directly in the command line.

  To add a key/value pair, use `--add <key> <value>`.
  To remove a key, use `--remove <key>`.
  To copy a key from one path to another, use `--copy <from> <to>`.
  To replace a key's value, use `--replace <key> <value>`.
  To test a key's value, use `--test <key> <value>`.
  To move a key from one path to another, use `--move <from> <to>`.
  """
  def __init__(self, option_strings, dest, nargs='+', metavar=('key', 'value'), **kwargs):
    opts = ["--add", "--remove", "--copy", "--replace", "--test", "--move"]
    super().__init__(opts, dest, nargs=nargs, metavar=metavar, **kwargs)
  def __call__(self, parser, namespace, value, option_string=None):
    def validate_key(key):
      key = key.replace("[", "/").replace("]", "")
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

class DataMapAction(argparse.Action):
  """Data Map Action
  
  A custom argparse action which allows for making key/value pairs from either literal values or files.
  This is fashioned after the kubectl params for secrets and configmaps, where you can specify a file or a literal value.

  For files you specify `--from-file <file name>` which will use the file name as the key and the contents of the file as the value. If you want to change the name of the key, then simply specify `--from-file <key>=<file name>`. If you want to use stdin, then use `--from-file -` which will use "stdin" as the key. You can even do `--from-file foo.txt=-` to use stdin and name the key.

  For literal values you specify `--from-literal <key>=<value>`. This will create a key/value pair in the data map. In this case the key and value must always be specified. 
  """
  def __init__(self, option_strings, dest, nargs='+', **kwargs):
    super(DataMapAction, self).__init__(option_strings, dest, nargs=nargs, **kwargs)
    self.__filetype = argparse.FileType()
  def __call__(self, parser, namespace, values, option_string=None):
    key = None 
    value = None
    items = getattr(namespace, self.dest, None)
    data = items if items else {}
    if option_string == "--from-file":
      key, value = self.__file_value(values[0])
    elif option_string == "--from-literal":
      key, value = self.__literal_value(values[0])
    data[key] = value
    setattr(namespace, self.dest, data)

  def __file_value(self, string):
    key = None
    fpath = None
    parts = string.split("=", 1)
    if len(parts) == 1:
      fpath = parts[0]
      key = "stdin" if fpath == "-" else os.path.basename(fpath)
    elif len(parts) == 2:
      key, fpath = parts
    f = self.__filetype(fpath)
    value = f.read().strip()
    return [key, value]
  
  def __literal_value(self, string):
    parts = string.split("=", 1)
    if len(parts) != 2:
      raise argparse.ArgumentTypeError("Literal values must be in the format key=value")
    return parts
