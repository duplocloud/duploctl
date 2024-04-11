#!/usr/bin/env python3
import datetime
import os
import semver
from git import Repo
from packaging.version import Version
import argparse

HERE = os.path.dirname(__file__)
CWD = os.path.join(HERE, '..')
UNRELEASED = "## [Unreleased]"
CHANGELOG = 'CHANGELOG.md'
CHANGELOG_OUT = os.path.join(CWD, CHANGELOG)
DIST = os.path.join(CWD, 'dist')
REPO = Repo(CWD)

parser = argparse.ArgumentParser(
  prog='version-bumper',
  description='A duploctl version bumper.',
)

parser.add_argument('action', type=str, help='The type of version bump to perform.', default="patch")
parser.add_argument('push', type=str, help='Push to remote?', default="false")

def get_changelog():
  with open(CHANGELOG, 'r') as f:
    return f.read()
  
def save_changelog(changelog, path):
  with open(path, 'w') as f:
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

def commit_changes(changelog, tag):
  msg = f"Release {tag}"
  email = os.environ.get('GITHUB_EMAIL', None)
  REPO.config_writer().set_value("user", "name", "Github Actions").release()
  REPO.config_writer().set_value("user", "email", email).release()
  REPO.index.add([CHANGELOG])
  REPO.index.commit(msg)
  REPO.create_tag(tag, message=msg)
  origin = REPO.remote(name='origin')
  origin.push()
  origin.push(tags=True)

def main():
  args = parser.parse_args()
  v = bump_version(args.action)
  t = f"v{v}"
  c = get_changelog()
  o = CHANGELOG_OUT # changelog path
  n = release_notes(c)
  c = replace_unreleased(c, v)
  if args.push != "true":
    v = REPO.head.reference
    t = v
    o = os.path.join(DIST, CHANGELOG)
  save_github_output(n, v, t)
  save_changelog(c, o)
  if args.push == "true":
    print(f"Pushing changes for v{v}")
    commit_changes(c, t)
  
if __name__ == '__main__':
  main()
