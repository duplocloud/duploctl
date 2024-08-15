from typing import Any
import requests

class GithubRepo:
  def __init__(self, token=None, repo_name="duploctl"):
    self.url = f"https://api.github.com/repos/duplocloud/{repo_name}"
    self.headers = {
      "Accept": "application/vnd.github.v3+json",
      "Authorization": f"token {token}",
    }

  def publish(self, tag, file, content) -> Any:
    parent = self.get_base_commit()
    base_tree = parent["object"]["sha"]
    tree = self.create_tree(base_tree, file, content)
    commit = self.create_commit(base_tree, tree, f"Bump version to {tag}")
    self.update_main(commit)
    self.create_tag(tag, commit)

  def get_base_commit(self):
    r = requests.get(f"{self.url}/git/refs/heads/main", headers=self.headers)
    return r.json()

  def create_tree(self, base_tree, file, content):
    r = requests.post(f"{self.url}/git/trees", headers=self.headers, json={
      "base_tree": str(base_tree),
      "tree": [{
        "path": file,
        "mode": "100644",
        "type": "blob",
        "content": content
      }]
    })
    return r.json()

  def create_commit(self, base_tree, tree, message):
    r = requests.post(f"{self.url}/git/commits", headers=self.headers, json={
      "message": message,
      "tree": tree["sha"],
      "parents": [base_tree],
    })
    return r.json()
  
  def update_main(self, commit):
    r = requests.patch(f"{self.url}/git/refs/heads/main", headers=self.headers, json={
      "sha": commit["sha"]
    })
    return r.json()
  
  def create_tag(self, tag, commit):
    r = requests.post(f"{self.url}/git/refs", headers=self.headers, json={
      "ref": f"refs/tags/{tag}",
      "sha": commit["sha"]
    })
    return r.json()
  
  def generate_release_notes(self, tag_name, previous_tag_name=None, target_commitish=None):
    body = {
      "tag_name": tag_name
    }
    if previous_tag_name:
      body["previous_tag_name"] = previous_tag_name
    if target_commitish:
      body["target_commitish"] = target_commitish
    r = requests.post(f"{self.url}/releases/generate-notes", headers=self.headers, json=body)
    return r.json()
