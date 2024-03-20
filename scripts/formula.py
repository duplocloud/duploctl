#!/usr/bin/env python3
import os
import requests
from importlib.metadata import version

def get_dependency(name):
  v = version(name)
  url = f"https://pypi.org/pypi/{name}/{v}/json"
  response = requests.get(url)
  data = response.json()
  sdist = list(filter(lambda x: x['packagetype'] == 'sdist', data['urls']))[0]
  return f"""
    resource "{name}" do
      url "{sdist['url']}"
      sha256 "{sdist['digests']['sha256']}"
    end
  """

tpl_path = 'scripts/formula.tpl.rb'
v   = os.sys.argv[1].replace('v', '')
url = f"https://github.com/duplocloud/duploctl/releases/download/v{v}/checksums.txt"
response = requests.get(url)
checksums = response.text.splitlines()
linux_sha = None 
macos_sha = None
pip_sha = None
for line in checksums:
  l = line.split(" ")
  if 'darwin' in line:
    macos_sha = l[0]
  elif 'linux' in line:
    linux_sha = l[0]
  elif 'duplocloud-client' in line:
    pip_sha = l[0]

dependencies = [
  'requests',
  'pyyaml',
  'cachetools',
  'jmespath'
]

with open(tpl_path, 'r') as tpl_file:
  tpl = tpl_file.read()
  formula = tpl.format(
    version=v, 
    linux_sha=linux_sha, 
    macos_sha=macos_sha,
    pip_sha=pip_sha,
    resources="".join([get_dependency(dep) for dep in dependencies])
  )
  os.makedirs('dist', exist_ok=True)
  with open('dist/duploctl.rb', 'w') as formula_file:
    formula_file.write(formula)
  print(formula)
