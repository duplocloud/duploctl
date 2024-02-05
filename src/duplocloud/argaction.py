import argparse
import yaml

class YamlAction(argparse.Action):
  def __init__(self, option_strings, dest, nargs=None, **kwargs):
    super().__init__(option_strings, dest, **kwargs)
  def __call__(self, parser, namespace, value, option_string=None):
    data = yaml.load(value, Loader=yaml.FullLoader)
    setattr(namespace, self.dest, data)
