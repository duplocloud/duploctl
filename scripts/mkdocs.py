import logging, re
import mkdocs.plugins as plugins
from jinja2 import Template, Environment
from jinja2.filters import FILTERS

log = logging.getLogger('mkdocs')

page_meta = None

def page_meta_filter(input):
    """Filter to access page meta data in markdown"""
    t = Template(input)
    return t.render(**page_meta)

def on_config(config, **kwargs):
    FILTERS['page_meta'] = page_meta_filter
    return config

def on_page_markdown(markdown, page, **kwargs):
    global page_meta
    page_meta = page.meta
    return markdown

def on_env(env: Environment, config, files, **kwargs): 
    return env

# def on_page_content(html, page, **kwargs):
#     # return html.replace('{kind}', page.meta.get('kind', 'unknown'))
#     t = Template(html)
#     return t.render(**page.meta)
