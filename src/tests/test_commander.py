import pathlib
import pytest 
# import unittest
import argparse
from duplocloud.commander import schema, resources, Command, get_parser, aliased_method, extract_args, available_resources, load_resource
from duplocloud.argtype import Arg, DataMapAction
from duplocloud.errors import DuploError
# from duplo_resource.service import DuploService
# from duplocloud.resource import DuploResource

dir = pathlib.Path(__file__).parent.resolve()

NAME = Arg("name", 
            help='A test name arg')

ENABLED = Arg("enabled", "-y",
              help='A test enabled arg',
              action="store_true",
              type=bool,
              default=False)
              
IMAGE = Arg("image", "-i", "--img",
            help='A test image arg',
            default="ubuntu")

class SomeResource():
  @Command("test")
  def tester(self, 
             # use shared arg
             name: NAME,
             # inline an Arg definition with alt flag and new dest based on arg name
             image_name: IMAGE="ubuntu",
             # a boolean arg too
             enabled: ENABLED=False,
             # foo should not be registered as an arg
             foo: str="bar"):
    print(name, image_name, foo, enabled)
  def not_a_command(self):
    pass

@pytest.mark.unit
def test_command_registration():
  qn = SomeResource.tester.__qualname__
  # assert qn is a key in schema
  assert qn in schema

@pytest.mark.unit
def test_extracting_args():
  args = extract_args(SomeResource.tester)
  assert len(args) == 3
  for arg in args:
    # assert arg is an Arg
    assert isinstance(arg, Arg)
    print(arg.__name__)
    if arg.__name__ == "image":
      assert arg.default == "ubuntu"
      assert arg.attributes["dest"] == "image_name"
    if arg.__name__ == "enabled":
      assert arg.attributes["action"] == "store_true"
      assert arg.default == False # noqa: E712
      assert isinstance(arg(True), bool)

@pytest.mark.unit
def test_using_parser():
  # now make sure the proper parser is returned
  args = extract_args(SomeResource.tester)
  assert (p := get_parser(args))
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

@pytest.mark.unit
def test_loading_service():
  assert (svc := load_resource("service")) # noqa: F841
  assert "service" in resources
  svcs = available_resources()
  assert "service" in svcs

@pytest.mark.unit
def test_arg_type():
  assert isinstance(NAME, Arg)
  name = NAME("foo")
  assert isinstance(name, str)

@pytest.mark.unit
def test_aliased_command():
  method = aliased_method(SomeResource, "test")
  assert method == "tester"

@pytest.mark.unit
def test_datamap_action():
  fname = "password.txt"
  password = "verysecretpassword"
  fpath = f"{dir}/files/{fname}"
  p = argparse.ArgumentParser()
  p.add_argument("--from-file", "--from-literal", dest="data", action=DataMapAction)
  args = [
    "--from-file", fpath,
    "--from-file", f"renamed={fpath}",
    "--from-literal", "foo=bar"
  ]
  ns = p.parse_args(args)
  assert ns.data == {
    "password.txt": password,
    "renamed": password,
    "foo": "bar"
  }
