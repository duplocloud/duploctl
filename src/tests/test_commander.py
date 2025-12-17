import pathlib
import pytest 
# import unittest
import argparse
from duplocloud.commander import schema, resources, Command, Resource, get_parser, aliased_method, extract_args, available_resources, load_resource, commands_for
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

# Test classes for schema_for testing
class ParentTestResource():
  @Command()
  def list(self):
    pass
  
  @Command("get")
  def find(self):
    pass
  
  @Command()
  def create(self):
    pass

@Resource("testchild")
class ChildTestResource(ParentTestResource):
  @Command()
  def update(self):
    pass
  
  @Command("get")  # Override parent's find method
  def find(self):
    pass

@Resource("teststandalone")
class StandaloneTestResource():
  @Command("ls")
  def list(self):
    pass
  
  @Command()
  def delete(self):
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

@pytest.mark.unit
def test_commands_for():
  # Test commands_for with child resource
  result = commands_for("testchild")
  
  # Should have 4 methods: list, create (from parent), update, find (overridden)
  assert len(result) == 4
  assert "list" in result
  assert "find" in result
  assert "create" in result
  assert "update" in result
  
  # Verify parent methods are included
  assert result["list"]["class"] == "ParentTestResource"
  assert result["list"]["method"] == "list"
  assert result["create"]["class"] == "ParentTestResource"
  
  # Verify child's own method
  assert result["update"]["class"] == "ChildTestResource"
  assert result["update"]["method"] == "update"
  
  # Verify overridden method uses child class
  assert result["find"]["class"] == "ChildTestResource"
  assert result["find"]["method"] == "find"
  assert result["find"]["aliases"] == ["get"]
  
  # Test with non-existent resource
  with pytest.raises(DuploError) as exc_info:
    commands_for("nonexistent")
  assert "Resource named nonexistent not found" in str(exc_info.value)

@pytest.mark.unit
def test_commands_for_no_parent():
  result = commands_for("teststandalone")
  
  # Should only have the resource's own methods
  assert len(result) == 2
  assert "list" in result
  assert "delete" in result
  
  # Verify methods
  assert result["list"]["class"] == "StandaloneTestResource"
  assert result["list"]["aliases"] == ["ls"]
  assert result["delete"]["class"] == "StandaloneTestResource"
  assert result["delete"]["aliases"] == []

