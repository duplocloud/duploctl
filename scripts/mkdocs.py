import os
import sys
import shutil
import logging, re
from jinja2 import Template
from jinja2.filters import FILTERS
from duplocloud.commander import ep
import duplocloud.args as args

# add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

log = logging.getLogger('mkdocs')
doc_dir = './dist/docs'
page_meta = None

include_pages = [
  "CONTRIBUTING.md",
  "CHANGELOG.md",
  "CODE_OF_CONDUCT.md",
  "SECURITY.md",
  "LICENSE",
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
  fp = f"{doc_dir}/{kind}.md"
  with open(fp, 'w') as f:
    f.write(f"""---
kind: {kind}
---
::: {ref}
""")
    
def gen_include_page(file):
  page = file if file.endswith('.md') else file + '.md'
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
  
def hello_filter(input):
  return f"Hello {input}"

def on_startup(**kwargs):
  copy_static()
  for e in ep:
    if e.name not in ignored:
      gen_resource_page(e)
  for f in include_pages:
    gen_include_page(f)

def on_config(config, **kwargs):
  copy_static()
  FILTERS['page_meta'] = page_meta_filter
  FILTERS['cli_arg'] = cli_arg_filter
  FILTERS['list_to_csv'] = list_to_csv_filter
  FILTERS['string_or_class_name'] = string_or_class_name_filter
  FILTERS['hello_there'] = hello_filter
  return config

def on_page_markdown(markdown, page, **kwargs):
  """Save the page meta data to be used in the page_meta_filter"""
  global page_meta
  page_meta = page.meta
  t = Template(markdown)
  return t.render(**page_meta)

