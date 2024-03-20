
def tostring(obj):
  """Converts a python object to a string.

  The default formatter with no fancy pants tranforming.

  Args:
    obj: The python object to convert.

  Returns:
    A string representing the object.
  """
  return str(obj)

def tojson(obj):
  """Converts a python object to a JSON string.

  Args:
    obj: The python object to convert.

  Returns:
    A JSON string representing the object.
  """
  import json
  return json.dumps(obj)

def toyaml(obj):
  """Converts a python object to a YAML string.

  Args:
    obj: The python object to convert.

  Returns:
    A YAML string representing the object.
  """
  import yaml
  return yaml.dump(obj)

def toenv(obj):
  """Converts a python object to a .env file format
  
  Args:
    obj: The python object to convert.
  
  Returns:
    A .env file format string representing the object.
  """
  envs = [f"{k}={v}" for k, v in obj.items()]
  return "\n".join(envs)

def tocsv(obj):
  """Converts a python object to a CSV string.

  Args:
    obj: The python object to convert.

  Returns:
    A CSV string representing the object.
  """
  import csv
  from io import StringIO
  if not isinstance(obj, list):
    obj = [obj]
  headers = obj[0].keys()
  output = StringIO()
  writer = csv.writer(output)
  writer.writerow(headers)
  for row in obj:
    writer.writerow(row.values())
  return output.getvalue()
