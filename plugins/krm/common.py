import sys
import os
import yaml
import re
import jsonpatch
import operator
from importlib.metadata import entry_points
# import importlib.resources as importlib_resources

from duplocloud.errors import DuploError
from . import files

def execute(fx: callable = None):
  """KRM Function Executor

  Use this to exectute any KRM function. By default the function to run will be 
  auto discovered from the apiVersion and kind of the functionConfig in the KRM ResourceList. 
  Otherwise you can pass in an ad hoc transformer on the fly as an argument. 

  This fully conforms to the Kustomize KRM function flow. 
  Read more about KRM here: 
  https://github.com/kubernetes-sigs/kustomize/blob/master/cmd/config/docs/api-conventions/functions-spec.md

  In the end the ResourceList is dumped to stdout, kustomize will take it from there to process your output. 

  Args:
    fx: An optional transformer function to run instead of using autodiscovery.

  Note:
    This is the main entry point to this cli application. 

  Example: 
    Using a custom transformer as krm function::

      from cubizoid import common as c

      def transform(krm):
        konfig = krm["functionConfig"] # the krm yaml which triggers the function
        # ... do kustom transforms to krm["items"]
        return krm
      c.execute(transform)

  """
  krm = krm_init() # builds the ResourceList from stdin
  if fx is None: # autodiscover function by default
    fx = load_function(krm["functionConfig"])
  try:
    dump(fx(krm))
  except Exception as e:
    raise DuploError(f"Error running function: {e}")

def resolve(krm: dict) -> dict:
  """Resolve KRM Function
  
  A helper to quickly autodiscover an installed function
  and then transform the given inputs by calling it. 

  Args:
    krm: A KRM ResourceList with an arbitrary functionConfig
  
  Returns:
    The transformed input. 
  """
  fx = load_function(krm["functionConfig"])
  return fx(krm)

def load_function(konfig: dict) -> callable:
    """Load Function
    
    This is the autodiscovery which uses the apiVersion and kind from the 
    KRM configuration to find the function in the registered python entrypoints. 
    For this to actually work the desired function must be registered in setup.cfg
    as an entrypoint using the lower case kind as the key under the group. 

    Args:
      konfig: The KRM configuration for the function. 

    Returns:
      The callable krm function
    """
    group = konfig["apiVersion"].split("/")[0]
    kind = konfig["kind"].lower()
    eps = entry_points()[group]
    # e = entry_points(group=group, name=kind)
    e = [ep for ep in eps if ep.name == kind][0]
    return e.load()
  
def dump(krm: dict):
  """Dump KRM Output  

  Performs the yaml dump which prints back to stdin. If the resource was run as a true KRM,
  then the dumped output is the ResourceList kind which is sent back into kustomize. 

  Args:
    krm: The final KRM ResourceList with all transformations. 
  """
  if "config.kubernetes.io/function" in krm["functionConfig"]["metadata"]["annotations"]:
    # print("Running krm function", file=sys.stderr)
    yaml.safe_dump(krm, sys.stdout, default_flow_style=False);
  else:
    # print("Running legacy plugin", file=sys.stderr)
    yaml.safe_dump_all(krm["items"], sys.stdout, default_flow_style=False);

def krm_init() -> dict:
  """KRM Initialization

  Initializes a KRM ResourceList from stdin. If running as a true krm function,
  ie the konfig has the proper annotations, then kustomize builds the ResourceList. 
  However, the function can still be run the legacy way where stdin is the ResourceList items
  and the konfig is the contents of the file from the last argument. 

  Returns:
    The KRM ResourceList with items and konfig loaded and ready. 
  """
  # if pipeline
  if not sys.stdin.isatty():
    res = list(yaml.safe_load_all(sys.stdin))
  else:
    res = []

  # if a ResourceList was passed as stdin
  if len(res) == 1 and res[0]["kind"] == "ResourceList":
    res[0]["type"] = "krm"
    return res[0]
  else:
    f = sys.argv[-1]
    if os.path.isfile(f):
      # raise DuploError("Could not load configuration: {}".format(f))
      conf = files.load_yaml(f)
    else:
      conf = {"metadata": {}}
    anno = conf["metadata"].get("annotations", {})
    anno["krm.type"] = "legacy"
    conf["metadata"]["annotations"] = anno
    if "annotations" not in conf["metadata"]:
      conf["metadata"]["annotations"] = {}
    return new_resource_list_object(conf, res)

# def konfig(name: str) -> dict:
#   pkg = importlib_resources.files("konfig")
#   lp = pkg / f"{name}.yaml"
#   content = lp.read_text(encoding="utf-8")
#   return yaml.safe_load(content)

def new_resource_list_object(konfig = {}, items = []):
  return {
    "apiVersion": "config.kubernetes.io/v1",
    "kind": "ResourceList",
    "functionConfig": konfig,
    "items": items,
    "results": []
  }

def new_list_object(name, items = []):
    return {
        "apiVersion": "v1",
        "kind": "List",
        "metadata": {
            "name": name
        },
        "items": items
    }

def query(items, target):
  """Query K8S Objects"""
  return [r for r in items if targeted(r, target)]

def apply_patches(target, patches):
  p = jsonpatch.JsonPatch(patches)
  return p.apply(target)

def mergeMeta(res, plugin):
  if "name" not in res["metadata"]:
    res["metadata"]["name"] = plugin["metadata"]["name"]
  if "namespace" not in res["metadata"] and "namespace" in plugin["metadata"]:
    res["metadata"]["namespace"] = plugin["metadata"]["namespace"]
  if "labels" in plugin["metadata"]:
    if "labels" not in res["metadata"]:
      res["metadata"]["labels"] = {}
    res["metadata"]["labels"] = {**res["metadata"]["labels"], **plugin["metadata"]["labels"], }
  
  # currently merging the annotations will cause the resource to be ignored when using krm functions
  # this happens because the krm config has config.kubernetes.io/local-config: 'true'
  # if "annotations" in plugin["metadata"]:
  #   if "annotations" not in res["metadata"]:
  #     res["metadata"]["annotations"] = {}
  #   res["metadata"]["annotations"] = {**res["metadata"]["annotations"], **plugin["metadata"]["annotations"], }
  return res

def targeted(res, target):

  # match apiVersion filter
  if "apiVersion" in target and not re.match(target["apiVersion"], res["apiVersion"]):
    return False

  # match by kind filter
  if "kind" in target and not re.match(target["kind"], res["kind"]):
    return False

  # match by name filter
  if "name" in target and not re.match(target["name"], res["metadata"]["name"]):
    return False

  # match by label selector
  if "matchLabels" in target:
    if "labels" not in res["metadata"]:
      return False
    labels = dict(res["metadata"]["labels"])
    if not dict(labels, **target["matchLabels"]) == labels:
      return False

  # match by annotations selector
  if "matchAnnotations" in target:
    if "annotations" not in res["metadata"]:
      return False
    annotations = dict(res["metadata"]["annotations"])
    if not dict(annotations, **target["matchAnnotations"]) == annotations:
      return False

  # if all checks passed or there were none at all
  return True

_default_stub = object()
def deepGet(obj, path, default=_default_stub, separator='/'):
    """
    found here: https://codereview.stackexchange.com/questions/139810/python-deep-get
    Gets arbitrarily nested attribute or item value.

    Args:
        obj: Object to search in.
        path (str, hashable, iterable of hashables): Arbitrarily nested path in obj hierarchy.
        default: Default value. When provided it is returned if the path doesn't exist.
            Otherwise the call raises a LookupError.
        separator: String to split path by.

    Returns:
        Value at path.

    Raises:
        LookupError: If object at path doesn't exist.

    Examples:
        >>> deep_get({'a': 1}, 'a')
        1

        >>> deep_get({'a': 1}, 'b')
        Traceback (most recent call last):
            ...
        LookupError: {u'a': 1} has no element at 'b'

        >>> deep_get(['a', 'b', 'c'], -1)
        u'c'

        >>> deep_get({'a': [{'b': [1, 2, 3]}, 'some string']}, 'a.0.b')
        [1, 2, 3]

        >>> class A(object):
        ...     def __init__(self):
        ...         self.x = self
        ...         self.y = {'a': 10}
        ...
        >>> deep_get(A(), 'x.x.x.x.x.x.y.a')
        10

        >>> deep_get({'a.b': {'c': 1}}, 'a.b.c')
        Traceback (most recent call last):
            ...
        LookupError: {u'a.b': {u'c': 1}} has no element at 'a'

        >>> deep_get({'a.b': {'Привет': 1}}, ['a.b', 'Привет'])
        1

        >>> deep_get({'a.b': {'Привет': 1}}, 'a.b/Привет', separator='/')
        1

    """
    # split after first slash or char, 
    # this means the original string must always include an extra separator in the front
    attributes = path[1:].split(separator)

    LOOKUPS = [getattr, operator.getitem, lambda obj, i: obj[int(i)]]
    try:
        for i in attributes:
            # replace any jsonpath like escapes
            i = i.replace('~0', '~').replace('~1', "/")
            for lookup in LOOKUPS:
                try:
                    obj = lookup(obj, i)
                    break
                except (TypeError, AttributeError, IndexError, KeyError,
                        UnicodeEncodeError, ValueError):
                    pass
            else:
                msg = "{obj} has no element at '{i}'".format(obj=obj, i=i)
                raise LookupError(msg.encode('utf8'))
    except Exception:
        if _default_stub != default:
            print("Found default stub")
            return default
        raise
    return obj
