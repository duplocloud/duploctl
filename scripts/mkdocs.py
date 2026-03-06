import os
import sys
import shutil
import logging
import re
import json
import inspect
import importlib
from jinja2 import Template
from jinja2.filters import FILTERS
from duplocloud.commander import ep, commands_for, extract_args
from duplocloud.argtype import Arg
import duplocloud.args as args
import duplocloud_sdk
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(HERE))
from project import Project, REPO_URL

log = logging.getLogger('mkdocs')
logging.basicConfig(level=logging.INFO)
doc_dir = './dist/docs'
page_meta = None
version = None

resource_nav = []
include_pages = [
  "README.md=index.md",
  "CONTRIBUTING.md",
  "CHANGELOG.md",
  "CODE_OF_CONDUCT.md",
  "SECURITY.md",
  "LICENSE=License.md",
]

ignored = [
  "aws",
  "mcp"
]

def copy_static():
  shutil.copytree('./wiki', doc_dir, dirs_exist_ok=True)

def _own_public_methods(cls):
  """Return names of public methods defined in the source of cls.

  Filters out runtime-injected methods (e.g. from _inject_tenant_scope)
  that exist in cls.__dict__ but whose source file doesn't match the
  class's own module.
  """
  try:
    cls_file = inspect.getfile(cls)
  except (TypeError, OSError):
    cls_file = None
  results = []
  for name, val in cls.__dict__.items():
    if name.startswith('_') or not callable(val):
      continue
    try:
      val_file = inspect.getfile(val)
    except (TypeError, OSError):
      continue
    if cls_file and val_file != cls_file:
      continue
    results.append(name)
  return results

def _method_ref(cls, method_name):
  """Return the fully-qualified mkdocstrings ref for a method.

  For methods defined directly on cls, returns module.ClassName.method.
  For inherited methods, walks the MRO to find the defining class and
  returns that class's module.ClassName.method instead.
  """
  fn = getattr(cls, method_name, None)
  if fn is None:
    return None
  defining_cls_name = fn.__qualname__.split('.')[0]
  for klass in cls.__mro__:
    if klass.__name__ == defining_cls_name:
      return f"{klass.__module__}.{klass.__qualname__}.{method_name}"
  return f"{cls.__module__}.{cls.__qualname__}.{method_name}"

def gen_resource_page(endpoint: str):
  cls_name = endpoint.value.split(':')[-1]
  kind = re.sub(r'^Duplo', '', cls_name)
  ref = endpoint.value.replace(':', '.')
  resource_name = endpoint.name
  page = f"{kind}.md"
  resource_nav.append({kind: page})
  fp = f"{doc_dir}/{page}"

  cls = endpoint.load()
  try:
    cmd_map = commands_for(resource_name)
  except Exception:
    cmd_map = {}

  own = _own_public_methods(cls)
  command_methods = sorted(cmd_map.keys())
  regular_methods = sorted(m for m in own if m not in cmd_map)

  member_opts = "    options:\n      heading_level: 3\n      show_root_heading: true\n      show_root_full_path: false"
  command_opts = member_opts + "\n      is_command: true"

  with open(fp, 'w') as f:
    f.write(f"---\nkind: {kind}\n---\n")
    f.write(f"::: {ref}\n    options:\n      members: false\n      inherited_members: false\n\n")
    if command_methods:
      f.write("## Commands\n\n")
      for m in command_methods:
        mref = _method_ref(cls, m)
        if mref:
          model = cmd_map[m].get("model")
          model_opt = f"\n      command_model: {model}" if model else ""
          f.write(f"::: {mref}\n{command_opts}{model_opt}\n\n")
    if regular_methods:
      f.write("## Methods\n\n")
      for m in regular_methods:
        f.write(f"::: {ref}.{m}\n{member_opts}\n\n")

def gen_include_page(include):
  parts = include.split('=')
  if len(parts) == 2:
    file, page = parts
  else:
    file = parts[0]
    page = file
  fp = f"{doc_dir}/{page}"
  if not os.path.exists(fp):
    with open(fp, 'w') as f:
      f.write(f"--8<-- \"{file}\"")

def page_meta_filter(input):
  """Filter to access page meta data in markdown"""
  t = Template(input)
  return t.render(**page_meta)

def cli_arg_filter(attr):
  return getattr(args, attr.name)

def list_to_csv_filter(input):
  return ', '.join(str(v) for v in input)

def string_or_class_name_filter(input):
  if isinstance(input, str):
    return input
  else:
    return getattr(input, "__name__", str(input))

def model_schema_filter(model_name):
  """Load a pydantic model by name and return its JSON schema."""
  model_cls = getattr(duplocloud_sdk, model_name, None)
  if model_cls and hasattr(model_cls, "model_json_schema"):
    return json.dumps(model_cls.model_json_schema(by_alias=True), indent=2)
  return None

def _arg_name_map():
  """Build a reverse lookup from Arg.__name__ to the Python variable name in args module."""
  result = {}
  for var_name in dir(args):
    obj = getattr(args, var_name)
    if isinstance(obj, Arg):
      result[obj.__name__] = var_name
  return result

_args_ref_map = _arg_name_map()

def command_args_filter(function_path, model=None):
  """Extract CLI arg metadata from a command method.

  Takes a dotted function path (e.g. 'duplocloud.resource.DuploResourceV3.create')
  and returns a list of arg dicts for the template.
  """
  parts = function_path.rsplit('.', 2)
  if len(parts) < 3:
    return []
  module_path = parts[0]
  cls_name = parts[1]
  method_name = parts[2]
  try:
    mod = importlib.import_module(module_path)
    cls = getattr(mod, cls_name, None)
    if cls is None:
      return []
    fn = getattr(cls, method_name, None)
    if fn is None:
      return []
    extracted = extract_args(fn)
  except Exception:
    return []
  result = []
  for a in extracted:
    action_raw = a.attributes.get("action")
    if isinstance(action_raw, str):
      action = action_raw
    elif action_raw is not None:
      action = getattr(action_raw, "__name__", str(action_raw))
    else:
      action = None
    flags = list(dict.fromkeys(a.flags))
    type_name = a.type_name
    if model and a.__name__ == "file":
      type_name = model
    var_name = _args_ref_map.get(a.__name__)
    args_anchor = f"duplocloud.args.{var_name}" if var_name else None
    result.append({
      "name": a.__name__,
      "flags": flags,
      "positional": a.positional,
      "type_name": type_name,
      "default": a.default,
      "env": a.env,
      "help": a.attributes.get("help", ""),
      "required": a.attributes.get("required", False),
      "action": action,
      "choices": a.attributes.get("choices"),
      "nargs": a.attributes.get("nargs"),
      "metavar": a.attributes.get("metavar"),
      "args_anchor": args_anchor,
    })
  return result

def on_startup(**kwargs):
  global version
  project = Project()
  version = str(project.latest_tag)
  os.makedirs('dist/docs', exist_ok=True)
  copy_static()
  for e in ep:
    if e.name not in ignored:
      gen_resource_page(e)
  for f in include_pages:
    gen_include_page(f)
  FILTERS['page_meta'] = page_meta_filter
  FILTERS['cli_arg'] = cli_arg_filter
  FILTERS['list_to_csv'] = list_to_csv_filter
  FILTERS['string_or_class_name'] = string_or_class_name_filter
  FILTERS['model_schema'] = model_schema_filter
  FILTERS['command_args'] = command_args_filter

def on_config(config):
  copy_static()
  config["docs_dir"] = "dist/docs"
  config["nav"].insert(3, {"Resources": resource_nav})
  return config

def on_page_markdown(markdown, page, config, **kwargs):
  """Save the page meta data to be used in the page_meta_filter"""
  global page_meta
  page_meta = page.meta
  t = Template(markdown)
  return t.render(
    version=version, 
    repo_url=REPO_URL, 
    **page_meta)

