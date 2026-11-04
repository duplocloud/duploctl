import argparse
import io

import pytest
import yaml

from duplocloud.argtype import YamlAction


def _parse(text: str):
  """Run YamlAction over a file-like value the way argparse would."""
  parser = argparse.ArgumentParser()
  parser.add_argument("-f", dest="file", action=YamlAction)
  ns = argparse.Namespace()
  parser._actions[-1](parser, ns, io.StringIO(text), "-f")
  return ns.file


@pytest.mark.unit
def test_yaml_action_loads_body():
  """A plain YAML/JSON body parses into python data."""
  body = _parse("Name: svc\nReplicas: 2\nEnv:\n- Name: A\n  Value: b\n")
  assert body == {"Name": "svc", "Replicas": 2,
                  "Env": [{"Name": "A", "Value": "b"}]}


@pytest.mark.unit
def test_yaml_action_rejects_python_tags():
  """Python object tags are refused rather than constructed."""
  with pytest.raises(yaml.constructor.ConstructorError):
    _parse("!!python/name:os.system\n")
