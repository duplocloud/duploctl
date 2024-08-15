import os
import sys
import shutil
import logging
import re
from jinja2 import Template
from jinja2.filters import FILTERS
from duplocloud.commander import ep
import duplocloud.args as args
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
  "aws"
]

def copy_static():
  shutil.copytree('./wiki', doc_dir, dirs_exist_ok=True)

def gen_resource_page(endpoint: str):
  cls = endpoint.value.split(':')[-1]
  kind = re.sub(r'^Duplo', '', cls)
  # these two refs are just so slightly different
  ref = endpoint.value.replace(':', '.')
  page = f"{kind}.md"
  resource_nav.append({kind: page})
  fp = f"{doc_dir}/{page}"
  with open(fp, 'w') as f:
    f.write(f"""---
kind: {kind}
---
::: {ref}
""")
    
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

