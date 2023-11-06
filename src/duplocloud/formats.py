
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
