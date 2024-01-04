from typing import NewType

class Arg(NewType):
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
    super().__init__(name, type)
    self.attributes = {}
    self._flags = flags
    # when actions is set then type param only needed for the NewType
    if action is None: 
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
