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
try:
  import duplocloud_sdk
except ImportError:
  duplocloud_sdk = None
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(HERE))
from project import Project, REPO_URL

log = logging.getLogger('mkdocs')
logging.basicConfig(level=logging.INFO)
doc_dir = './dist/docs'
# Link corrected copies of the root files, used as snippet sources.
include_dir = './dist/includes'
page_meta = None
version = None

resource_nav = []
include_pages = [
  "README.md=index.md",
  "CONTRIBUTING.md",
  # staged as Changelog.md to match the url published in pyproject.toml
  "CHANGELOG.md=Changelog.md",
  "CODE_OF_CONDUCT.md",
  "SECURITY.md",
  "LICENSE=License.md",
]

ignored = [
  "aws",
  "mcp"
]

# The branch the site is built from, used to link back at repo files.
repo_branch = "main"

# Repo paths with a better destination than the raw Github blob url.
link_overrides = {
  "plugins": "/plugins/aws/",
  "wiki": f"{REPO_URL}/wiki",
}

# The target of an inline markdown link, ie ./foo.md in [foo](./foo.md).
link_re = re.compile(r'(?<=\]\()\s*([^)\s]+)')

def copy_static():
  shutil.copytree('./wiki', doc_dir, dirs_exist_ok=True)

def staged_pages():
  """Map each root file to the doc page it is staged as."""
  return {i.split('=')[0]: i.split('=')[-1] for i in include_pages}

def rewrite_link(target: str, pages: dict) -> str:
  """Rewrite a repo relative link target so it resolves on the site.

  Github resolves these against the repo root, but the site serves the
  same file at /<Page>/ so the browser resolves them against that page
  url instead and 404s. Links pointing at another staged page stay
  relative, everything else points back at the repo on Github.

  Args:
    target: The raw link target as written in the root file.
    pages: Map of root file to staged page name.

  Returns:
    target: The target rewritten for the doc site.
  """
  # already portable, ie absolute urls, anchors and site absolute paths
  if target.startswith(("http://", "https://", "//", "/", "#", "mailto:")):
    return target
  path, sep, anchor = target.partition('#')
  clean = path[2:] if path.startswith('./') else path
  clean = clean.rstrip('/')
  if not clean:
    return target
  if clean in pages:
    return pages[clean] + sep + anchor
  if clean in link_overrides:
    return link_overrides[clean]
  if os.path.isdir(clean):
    return f"{REPO_URL}/tree/{repo_branch}/{clean}/"
  if os.path.isfile(clean):
    return f"{REPO_URL}/blob/{repo_branch}/{clean}"
  # unknown target, leave it alone so the mkdocs warning still fires
  log.warning(f"unresolved link target '{target}' in staged docs")
  return target

def stage_include(include):
  """Stage a link corrected copy of a root file for the snippet include."""
  file = include.split('=')[0]
  with open(file, 'r') as f:
    content = f.read()
  pages = staged_pages()
  content = link_re.sub(lambda m: rewrite_link(m.group(1), pages), content)
  fp = f"{include_dir}/{file}"
  with open(fp, 'w') as f:
    f.write(content)

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
    f.write(f"---\nkind: {kind}\ncommand: {resource_name}\n---\n")
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
  if duplocloud_sdk is None:
    return None
  model_cls = getattr(duplocloud_sdk, model_name, None)
  if model_cls and hasattr(model_cls, "model_json_schema"):
    return json.dumps(model_cls.model_json_schema(by_alias=True), indent=2)
  return None

def command_args_filter(function_path):
  """Extract Arg objects from a command method for the template."""
  parts = function_path.rsplit('.', 2)
  if len(parts) < 3:
    return []
  try:
    mod = importlib.import_module(parts[0])
    cls = getattr(mod, parts[1], None)
    fn = getattr(cls, parts[2], None) if cls else None
    return extract_args(fn) if fn else []
  except Exception:
    return []

def args_ref_filter(arg):
  """Map an Arg to its Args.md anchor (e.g. duplocloud.args.HOST)."""
  for var_name in dir(args):
    obj = getattr(args, var_name)
    if isinstance(obj, Arg) and obj.__name__ == arg.__name__:
      return f"duplocloud.args.{var_name}"
  return None

def on_startup(**kwargs):
  global version
  project = Project()
  version = str(project.latest_tag)
  os.makedirs('dist/docs', exist_ok=True)
  os.makedirs('dist/includes', exist_ok=True)
  copy_static()
  for e in ep:
    if e.name not in ignored:
      gen_resource_page(e)
  for f in include_pages:
    stage_include(f)
    gen_include_page(f)
  FILTERS['page_meta'] = page_meta_filter
  FILTERS['cli_arg'] = cli_arg_filter
  FILTERS['list_to_csv'] = list_to_csv_filter
  FILTERS['string_or_class_name'] = string_or_class_name_filter
  FILTERS['model_schema'] = model_schema_filter
  FILTERS['command_args'] = command_args_filter
  FILTERS['args_ref'] = args_ref_filter

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

