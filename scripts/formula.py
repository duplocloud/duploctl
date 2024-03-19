#!/usr/bin/env python3
import os
import requests

tpl_path = 'scripts/formula.tpl.rb'
version   = os.sys.argv[1].replace('v', '')
url = f"https://github.com/duplocloud/duploctl/releases/download/v{version}/checksums.txt"
response = requests.get(url)
checksums = response.text.splitlines()
linux_sha = None 
macos_sha = None
for line in checksums:
  if 'darwin' in line:
    macos_sha = line.split(" ")[0]
  elif 'linux' in line:
    linux_sha = line.split(" ")[0]

with open(tpl_path, 'r') as tpl_file:
  tpl = tpl_file.read()
  formula = tpl.format(version=version, linux_sha=linux_sha, macos_sha=macos_sha)
  os.makedirs('dist', exist_ok=True)
  with open('dist/duploctl.rb', 'w') as formula_file:
    formula_file.write(formula)
    print(formula)
