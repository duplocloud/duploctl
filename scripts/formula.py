#!/usr/bin/env python3
import os
import requests
import toml
import re
from importlib.metadata import version

def make_resource(name):
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

# get started
f = open('pyproject.toml')
v = os.sys.argv[1].replace('v', '')

# Build the homebrew pip resources from the project dependencies
data = toml.load(f)
pattern = '|'.join(map(re.escape, ['>=', '<=', '==', '!=']))
resources = []
for dep in data['project']['dependencies']:
  name, _ = re.split(pattern, dep, 1)
  res = make_resource(name)
  resources.append(res)

# get the checksums from the github release
repo_url = data['project']['urls']['Repository']
description = data['project']['description']
url = f"{repo_url}/releases/download/v{v}/checksums.txt"
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
    repo_url=repo_url,
    description=description,
    version=v, 
    linux_sha=linux_sha, 
    macos_sha=macos_sha,
    pip_sha=pip_sha,
    resources="".join(resources)
  )
  os.makedirs('dist', exist_ok=True)
  with open('dist/duploctl.rb', 'w') as formula_file:
    formula_file.write(formula)
    print(formula)
