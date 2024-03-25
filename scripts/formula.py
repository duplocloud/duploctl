#!/usr/bin/env python3
import os
import requests
import toml
import re
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

# Build the homebrew pip resources from the project dependencies
f = open('pyproject.toml')
data = toml.load(f)
dependencies = data['project']['dependencies']
operators = ['>=', '<=', '==', '!=']
pattern = '|'.join(map(re.escape, operators))
deps = []
for dep in dependencies:
  name, _ = re.split(pattern, dep, 1)
  deps.append(name)
resources = "".join([get_dependency(dep) for dep in deps])

# get the checksums from the github release
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

# finally build and print the formula from template
with open('scripts/formula.tpl.rb', 'r') as tpl_file:
  tpl = tpl_file.read()
  formula = tpl.format(
    version=v, 
    linux_sha=linux_sha, 
    macos_sha=macos_sha,
    pip_sha=pip_sha,
    resources=resources
  )
  os.makedirs('dist', exist_ok=True)
  with open('dist/duploctl.rb', 'w') as formula_file:
    formula_file.write(formula)
    print(formula)
