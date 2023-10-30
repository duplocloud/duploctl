import pytest 
import unittest

import argparse

from .commander import schema, Command, get_parser, load_service
from .types import Arg
from .errors import DuploError
from duplo_resource.service import DuploService
from .resource import DuploResource

NAME = Arg("name", 
            help='A test name arg')

class SomeResource():
  @Command()
  def tester(self, 
             # use shared arg
             name: NAME,
             # inline an Arg definition with alt flag and new dest based on arg name
             image_name: Arg("image", "-i", "--img",
                        help='A test image arg')="ubuntu",
             # foo should not be registered as an arg
             foo: str="bar"):
    print(name, image_name, foo)
  def not_a_command(self):
    pass

def test_command_registration():
  qn = SomeResource.tester.__qualname__
  # assert qn is a key in schema
  assert qn in schema
  assert len(schema[qn]) == 2
  for arg in schema[qn]:
    # assert arg is an Arg
    assert isinstance(arg, Arg)
    if arg.__name__ == "image":
      assert arg.attributes["default"] == "ubuntu"
      assert arg.attributes["dest"] == "image_name"

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
  # assert isinstance(svc, DuploResource)
