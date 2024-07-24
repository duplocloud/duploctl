import os
import shutil
import logging, re
from jinja2 import Template
from jinja2.filters import FILTERS
from duplocloud.commander import ep

log = logging.getLogger('mkdocs')
doc_dir = './dist/docs'
page_meta = None

include_pages = [
  "CONTRIBUTING.md",
  "CHANGELOG.md",
]

ignored = [
  "aws"
]

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
  fp = f"{doc_dir}/{file}"
  if not os.path.exists(fp):
    with open(fp, 'w') as f:
      f.write(f"--8<-- \"{file}\"")

def page_meta_filter(input):
  """Filter to access page meta data in markdown"""
  t = Template(input)
  return t.render(**page_meta)

def on_startup(**kwargs):
  shutil.copytree('./wiki', doc_dir, dirs_exist_ok=True)
  for e in ep:
    if e.name not in ignored:
      gen_resource_page(e)
  for f in include_pages:
    gen_include_page(f)

def on_config(config, **kwargs):
  FILTERS['page_meta'] = page_meta_filter
  return config

def on_page_markdown(markdown, page, **kwargs):
  """Save the page meta data to be used in the page_meta_filter"""
  global page_meta
  page_meta = page.meta
  return markdown

