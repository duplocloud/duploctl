#!/usr/bin/env python3
import argparse
import sys
import os
import requests
import toml
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(HERE))
# from importlib.metadata import version
from gha import GithubRepo
from project import Project

class HomebrewFormula:

  def __init__(self, token, tag=None):
    self.repo = GithubRepo(token, "homebrew-tap")
    self.project = Project()
    f = open('pyproject.toml')
    self.pyproject = toml.load(f)
    self.repo_url = self.pyproject['project']['urls']['Repository']
    self.description = self.pyproject['project']['description']
    self.tpl_file = 'scripts/formula.tpl.rb'
    self.out_file = 'duploctl.rb'
    self.version = tag.replace("v", "") if tag else self.project.latest_tag

  def publish(self, push="false"):
    formula = self.build_formula()
    print(formula)
    if push == "true":
      print("Pushing to remote")
      self.repo.publish(f"duploctl-v{self.version}", 'Formula/duploctl.rb', formula)
    else:
      self.project.dist_file(self.out_file, formula)

  def make_resource(self, requirement):
    name, version = requirement.split("==")
    url = f"https://pypi.org/pypi/{name}/{version}/json"
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
    with open('requirements.txt', 'r') as f:
      resources = [self.make_resource(r) for r in f.read().splitlines()]
      return "".join(resources)
  
  def get_shas(self):
    url = f"{self.repo_url}/releases/download/v{self.version}/checksums.txt"
    response = requests.get(url)
    checksums = response.text.splitlines()
    shas = {
      "linux_sha_amd64": None,
      "linux_sha_arm64": None,
      "macos_sha_amd64": None,
      "macos_sha_arm64": None,
      "pip_sha": None
    }
    for line in checksums:
      l = line.split(" ")
      if 'darwin-amd64' in line:
        shas["macos_sha_amd64"] = l[0]
      if 'darwin-arm64' in line:
        shas["macos_sha_arm64"] = l[0]
      elif 'linux-amd64' in line:
        shas["linux_sha_amd64"] = l[0]
      elif 'linux-arm64' in line:
        shas["linux_sha_arm64"] = l[0]
      elif 'duplocloud_client' in line:
        shas["pip_sha"] = l[0]
    return shas
  
  def build_formula(self):
    shas = self.get_shas()
    resources = self.make_resources()
    with open(self.tpl_file, 'r') as tpl_file:
      tpl = tpl_file.read()
      return tpl.format(
        repo_url=self.repo_url,
        description=self.description,
        version=self.version, 
        resources=resources,
        **shas
      )
  
if __name__ == '__main__':
  parser = argparse.ArgumentParser(
    prog='tap-formula',
    description='Pushes formula to tap',
  )

  parser.add_argument('--tag', type=str, help='A version tag to use.', default=None)
  parser.add_argument('--push', type=str, help='Push to remote?', default="false")
  parser.add_argument('--token', type=str, help='Github token', default=os.environ.get('GITHUB_TOKEN'))

  args = parser.parse_args()

  brew = HomebrewFormula(args.token, args.tag)
  brew.publish(args.push)

