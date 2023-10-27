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
    default (str): The default value to use for the argument.
    choices (list): The choices to use for the argument.
    required (bool): Whether the argument is required.
    help (str): The help text to use for the argument.
    metavar (str): The metavar to use for the argument.
    dest (str): The destination to use for the argument.
  """
  attributes = {}
  def __init__(self, 
              name, 
              flag=None, 
              type=str, 
              action=None, 
              nargs=None, 
              const=None, 
              default=None, 
              choices=None, 
              required=None, 
              help=None, 
              metavar=None, 
              dest=None):
    super().__init__(name, type)
    self.flag = flag
    self._set_attribute("type", type)
    self._set_attribute("action", action)
    self._set_attribute("nargs", nargs)
    self._set_attribute("const", const)
    self._set_attribute("default", default)
    self._set_attribute("choices", choices)
    self._set_attribute("required", required)
    self._set_attribute("help", help)
    self._set_attribute("metavar", metavar)
    self._set_attribute("dest", dest)
  def _set_attribute(self, key, value):
    if value is not None:
      self.attributes[key] = value
  @property
  def flags(self):
    if self.flag is None:
      return [self.__name__]
    return [self.flag, f"--{self.__name__}"]
