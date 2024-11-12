from pathlib import Path
import requests
import yaml
import json
import sys
from duplocloud.errors import DuploError

def get_file_contents(file: str) -> str:
  """Get File Contents
  
  Discovers the kind of file and loads its content. 

  Args:
    file: The path to some file as a string. 

  Returns:
    The content of the file at the specified path. 
  """
  if file.startswith("http"):
    r = requests.get(file, allow_redirects=True)
    return r.content
  else:
    return Path(file).read_text()

def discover_file_type(file: str) -> str:
  """Discover File Type
  
  From the given path to a file, try and discover the files content type. 
  Currently only json and yaml are supported as specific file types.
  Everything else is simply some text. 

  Args:
    file: The string value of the path to a file. 

  Returns:
    The content type of the file.
  """
  inferredType = Path(file).suffix
  # print("inferredType = "+inferredType)
  if inferredType in [".yaml", ".yml"]:
    return "yaml"
  elif inferredType == ".json":
    return "json"
  else:
    return "na"

def load_yaml(file: str, all: bool = False) -> dict:
  """Load YAML File
  
  Simply specify the path to a yaml file and the object within 
  is loaded as a dictionary. 

  Args:
    file: Path to the yaml file
  
  Returns:
    The dictionary parsed from the yaml file. 
  
  Example:
    All you have to do is point to the file::

      from cubizoid import files as f
      yamls = f.load_yaml('../path/to/my.yaml')
  """
  try:
    c = get_file_contents(file)
    y = yaml.safe_load_all(c) if all else yaml.safe_load(c)
  except yaml.YAMLError as exc:
    print("Error parsing input", file=sys.stderr)
    sys.exit(1)
  return y

def parse_from(contents: str, mimeType: str = "yaml") -> dict:
  """Parse Content From
  
  Parses the contents of a file to the desired content type. 

  Args:
    contents (str): The contents extracted from a file as text. 
    mimeType (str): Currently supported values are json and yaml. 
  
  Returns:
    The dictionary parsed from the content. 
  """
  if mimeType == "yaml":
    return yaml.safe_load(contents)
  elif mimeType == "json":
    return json.loads(contents)
  else:
    raise DuploError("Only json and yaml files may be parsed to objects")

def parse_to(obj, mimeType = "yaml") -> str:
  """Parse Object To
  
  Parses a python dictionary to formatted text specific to the mime type. 
  Basically dictionary to json or yaml as a string. 

  Args:
    obj: The object to be stringified into the mime type. 
    mimeType: Currently supported values are json and yaml.

  Returns:
    The mime types textual representation of the object.  
  """
  if mimeType == "yaml":
    return yaml.safe_dump(obj)
  elif mimeType == "json":
    return json.dumps(obj)
  else:
    raise DuploError("Objects may only be dumped to yaml or json")
