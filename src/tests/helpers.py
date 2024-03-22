import yaml
import pathlib

def get_test_data(name):
  # get the directory this file is in
  dir = pathlib.Path(__file__).parent.resolve()
  f = f"{dir}/data/{name}.yaml"
  with open(f, 'r') as stream:
    return yaml.safe_load(stream)
