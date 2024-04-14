#!/usr/bin/env python3
import datetime
import os
import semver
from git import Repo
from packaging.version import Version
import argparse
import requests

HERE = os.path.dirname(__file__)
CWD = os.getcwd()
UNRELEASED = "## [Unreleased]"
CHANGELOG = os.path.join(CWD, 'CHANGELOG.md')
DIST = os.path.join(CWD, 'dist')
REPO = Repo(CWD)
GHAPI="https://api.github.com/repos/duplocloud/duploctl/git"

parser = argparse.ArgumentParser(
  prog='version-bumper',
  description='A duploctl version bumper.',
)

parser.add_argument('action', type=str, help='The type of version bump to perform.', default="patch")
parser.add_argument('push', type=str, help='Push to remote?', default="false")
parser.add_argument('token', type=str, help='Github token', default=os.environ.get('GITHUB_TOKEN'))

def get_changelog():
  with open(CHANGELOG, 'r') as f:
    return f.read()
  
def save_changelog(changelog):
  with open(CHANGELOG, 'w') as f:
    f.write(changelog)
  
def release_notes(changelog):
  inblock = False
  msg = []
  for line in changelog.splitlines():
    if line.startswith(UNRELEASED):
      inblock = True
      continue
    if inblock and line.startswith("## ["):
      break
    if inblock:
      msg.append(line.strip())
  return "\n".join(msg)

def replace_unreleased(changelog, version):
  # get todays date formatted like 2023-03-05
  date = datetime.datetime.now().strftime("%Y-%m-%d")
  new_notes = f"{UNRELEASED}\n\n## [{version}] - {date}"
  return changelog.replace(UNRELEASED, new_notes)

def latest_tag():
  latest = Version("0.0.0")
  for t in REPO.tags:
    v = Version(t.name[1:])
    if v > latest:
      latest = v
  return semver.VersionInfo.parse(str(latest))

def bump_version(action: str="patch"):
  latest = latest_tag()
  if action == "major":
    return latest.bump_major()
  if action == "minor":
    return latest.bump_minor()
  if action == "patch":
    return latest.bump_patch()
  return latest

def save_github_output(notes, version, tag):
  outputs = os.environ.get('GITHUB_OUTPUT', './.github/output')
  # append to the end of the file
  with open(outputs, 'a') as f:
    f.write(f"version={version}\n")
    f.write(f"tag={tag}\n")
  # make sure the dist folder exists
  os.makedirs(DIST, exist_ok=True)
  with open(f"{DIST}/notes.md", 'w') as f:
    f.write(notes)

def commit_gha_changes(tag, token, changelog):
  base_tree = REPO.head.object.hexsha
  headers = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {token}",
  }
  # first make a tree, basically staging the changes
  r = requests.post(f"{GHAPI}/trees", headers=headers, json={
    "base_tree": str(base_tree),
    "tree": [{
      "path": "CHANGELOG.md",
      "mode": "100644",
      "type": "blob",
      "content": changelog
  }]})
  tree = r.json()
  # commit the changed changelog
  r = requests.post(f"{GHAPI}/commits", headers=headers, json={
    "message": f"Bump version to {tag}",
    "tree": tree["sha"],
    "parents": [base_tree],
  })
  commit = r.json()
  print("The commit object")
  print(commit)
  # update the main branch to point to the new commit
  r = requests.patch(f"{GHAPI}/refs/heads/main", headers=headers, json={
    "sha": commit["sha"]
  })
  print("The ref object")
  print(r.json())
  # create a lightweight tag for the commit
  r = requests.post(f"{GHAPI}/refs", headers=headers, json={
    "ref": f"refs/tags/{tag}",
    "sha": commit["sha"]
  })
  ref = r.json()
  print("The ref object")
  print(ref)

def commit_changes(tag):
  msg = f"Release {tag}"
  REPO.config_writer().set_value("user", "name", "duploctl[bot]").release()
  REPO.config_writer().set_value("user", "email", "123456789+duploctl[bot]@users.noreply.github.com").release()
  print(f"Committing changes for {tag} {CHANGELOG}")
  REPO.index.add([CHANGELOG])
  REPO.index.commit(msg)
  REPO.create_tag(tag, message=msg)
  origin = REPO.remote(name='origin')
  # can't push on main branch
  origin.push() 
  origin.push(tags=True)

def main():
  args = parser.parse_args()
  v = bump_version(args.action)
  t = f"v{v}"
  c = get_changelog()
  n = release_notes(c)
  c = replace_unreleased(c, v)
  if args.push != "true":
    v = REPO.head.reference
    t = v
  save_github_output(n, v, t)
  save_changelog(c)
  if args.push == "true":
    print(f"Pushing changes for v{v}")
    commit_gha_changes(t, args.token, c)
  
if __name__ == '__main__':
  main()
