#!/usr/bin/env python3
import argparse
import sys
import os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(HERE))
import requests
import toml
import re
from importlib.metadata import version
from gha import GithubRepo

class HomebrewFormula:

  def __init__(self, token, tag=None):
    self.repo = GithubRepo(token, "homebrew-tap")
    f = open('pyproject.toml')
    self.pyproject = toml.load(f)
    self.repo_url = self.pyproject['project']['urls']['Repository']
    self.description = self.pyproject['project']['description']
    self.tpl_file = 'scripts/formula.tpl.rb'
    self.out_file = 'duploctl.rb'
    self.version = tag.replace("v", "") if tag else self.repo.latest_tag()

  def publish(self, push="false"):
    formula = self.build_formula()
    print(formula)
    if push == "true":
      print("Pushing to remote")
      self.repo.publish(f"duploctl-v{self.version}", 'Formula/duploctl.rb', formula)
    else:
      self.repo.dist_file(self.out_file, formula)

  def make_resource(self, name):
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
  
  def make_resources(self):
    pattern = '|'.join(map(re.escape, ['>=', '<=', '==', '!=']))
    resources = []
    for dep in self.pyproject['project']['dependencies']:
      name, _ = re.split(pattern, dep, 1)
      res = self.make_resource(name)
      resources.append(res)
    return "".join(resources)
  
  def get_shas(self):
    url = f"{self.repo_url}/releases/download/v{self.version}/checksums.txt"
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
      elif 'duplocloud_client' in line:
        pip_sha = l[0]
    return (linux_sha, macos_sha, pip_sha)
  
  def build_formula(self):
    with open(self.tpl_file, 'r') as tpl_file:
      tpl = tpl_file.read()
      linux_sha, macos_sha, pip_sha = self.get_shas()
      resources = self.make_resources()
      formula = tpl.format(
        repo_url=self.repo_url,
        description=self.description,
        version=self.version, 
        linux_sha=linux_sha, 
        macos_sha=macos_sha,
        pip_sha=pip_sha,
        resources=resources
      )
      return formula
  
  
if __name__ == '__main__':
  parser = argparse.ArgumentParser(
    prog='tap-formula',
    description='Pushes formula to tap',
  )

  parser.add_argument('--tag', type=str, help='A version tag to use.', default=None)
  parser.add_argument('--push', type=str, help='Push to remote?', default="false")
  parser.add_argument('--token', type=str, help='Github token', default=os.environ.get('GITHUB_TOKEN'))

  args = parser.parse_args()

  print(f"Will publish version {args.tag}")

  brew = HomebrewFormula(args.token, args.tag)
  brew.publish(args.push)

