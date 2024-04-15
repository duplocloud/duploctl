from typing import Any
import requests
from git import Repo
import os
from packaging.version import Version
import semver

CWD = os.getcwd()

class GithubRepo:
  def __init__(self, token, repo_name="duploctl"):
    self.repo = Repo(CWD)
    self.url = f"https://api.github.com/repos/duplocloud/{repo_name}/git"
    self.headers = {
      "Accept": "application/vnd.github.v3+json",
      "Authorization": f"token {token}",
    }

  @property
  def ref(self):
    return self.repo.head.reference

  def publish(self, tag, file, content) -> Any:
    parent = self.get_base_commit()
    base_tree = parent["object"]["sha"]
    tree = self.create_tree(base_tree, file, content)
    print(tree)
    commit = self.create_commit(base_tree, tree, f"Bump version to {tag}")
    print(commit)
    ref = self.update_main(commit)
    print(ref)
    tag = self.create_tag(tag, commit)
    print(tag)

  def get_base_commit(self):
    r = requests.get(f"{self.url}/refs/heads/main", headers=self.headers)
    return r.json()

  def create_tree(self, base_tree, file, content):
    r = requests.post(f"{self.url}/trees", headers=self.headers, json={
    "base_tree": str(base_tree),
    "tree": [{
      "path": file,
      "mode": "100644",
      "type": "blob",
      "content": content
    }]})
    return r.json()

  def create_commit(self, base_tree, tree, message):
    r = requests.post(f"{self.url}/commits", headers=self.headers, json={
      "message": message,
      "tree": tree["sha"],
      "parents": [base_tree],
    })
    return r.json()
  
  def update_main(self, commit):
    r = requests.patch(f"{self.url}/refs/heads/main", headers=self.headers, json={
      "sha": commit["sha"]
    })
    return r.json()
  
  def create_tag(self, tag, commit):
    r = requests.post(f"{self.url}/refs", headers=self.headers, json={
      "ref": f"refs/tags/{tag}",
      "sha": commit["sha"]
    })
    ref = r.json()

  def latest_tag(self):
    latest = Version("0.0.0")
    for t in self.repo.tags:
      v = Version(t.name[1:])
      if v > latest:
        latest = v
    return semver.VersionInfo.parse(str(latest))
  
  def bump_version(self, action: str="patch"):
    latest = self.latest_tag()
    if action == "major":
      return latest.bump_major()
    if action == "minor":
      return latest.bump_minor()
    if action == "patch":
      return latest.bump_patch()
    return latest
  
  def dist_file(self, file, content):
    os.makedirs('dist', exist_ok=True)
    with open(f"dist/{file}", 'w') as f:
      f.write(content)
