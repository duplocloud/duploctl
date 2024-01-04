import pytest 
import unittest

import argparse

from .commander import schema, resources, Command, get_parser, load_service, available_resources
from .argtype import Arg
from .errors import DuploError
from duplo_resource.service import DuploService
from .resource import DuploResource

NAME = Arg("name", 
            help='A test name arg')

ENABLED = Arg("enabled", "-y",
              help='A test enabled arg',
              action="store_true",
              type=bool)

class SomeResource():
  @Command()
  def tester(self, 
             # use shared arg
             name: NAME,
             # inline an Arg definition with alt flag and new dest based on arg name
             image_name: Arg("image", "-i", "--img",
                        help='A test image arg')="ubuntu",
            # a boolean arg too
            enabled: ENABLED=False,
             # foo should not be registered as an arg
             foo: str="bar"):
    print(name, image_name, foo, enabled)
  def not_a_command(self):
    pass

def test_command_registration():
  qn = SomeResource.tester.__qualname__
  # assert qn is a key in schema
  assert qn in schema
  assert len(schema[qn]) == 3
  for arg in schema[qn]:
    # assert arg is an Arg
    assert isinstance(arg, Arg)
    if arg.__name__ == "image":
      assert arg.attributes["default"] == "ubuntu"
      assert arg.attributes["dest"] == "image_name"
    if arg.__name__ == "enabled":
      assert arg.attributes["action"] == "store_true"
      assert arg.attributes["default"] == False
      assert isinstance(arg(True), bool)

def test_using_parser():
  # first make sure the proper error is raised when the function is not registered
  try:
    get_parser(SomeResource.not_a_command)
  except DuploError as e:
    assert e.code == 3
    assert e.message == "Function named SomeResource.not_a_command not registered as a command."
  # now make sure the proper parser is returned
  assert (p := get_parser(SomeResource.tester))
  assert isinstance(p, argparse.ArgumentParser)
  # test with no args and get defaults
  args = ["foo"]
  parsed_args = p.parse_args(args)
  assert parsed_args.name == "foo"
  assert parsed_args.image_name == "ubuntu"
  # test with image set
  args = ["bar", "--img", "alpine"]
  parsed_args = p.parse_args(args)
  assert parsed_args.name == "bar"
  assert parsed_args.image_name == "alpine"
  # one more time with --image
  args = ["baz", "--image", "splunz:latest"]
  parsed_args = p.parse_args(args)
  assert parsed_args.name == "baz"
  assert parsed_args.image_name == "splunz:latest"

def test_loading_service():
  assert (svc := load_service("service"))
  assert "service" in resources
  svcs = available_resources()
  assert "service" in svcs

def test_arg_type():
  assert isinstance(NAME, Arg)
  name = NAME("foo")
  assert isinstance(name, str)


