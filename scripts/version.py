#!/usr/bin/env python3
import datetime
import argparse
import sys
import os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(HERE))
from gha import GithubRepo

UNRELEASED = "## [Unreleased]"
CHANGELOG = 'CHANGELOG.md'

def get_changelog():
  with open(CHANGELOG, 'r') as f:
    return f.read()
  
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

def save_github_output(notes, version, tag):
  """Save the tag and version in github output file"""
  outputs = os.environ.get('GITHUB_OUTPUT', './.github/output')
  with open(outputs, 'a') as f:
    f.write(f"version={version}\n")
    f.write(f"tag={tag}\n")

def publish(action, push, token):
  repo = GithubRepo(token)
  v = repo.bump_version(action)
  t = f"v{v}"
  c = get_changelog()
  n = release_notes(c)
  c = replace_unreleased(c, v)
  if push != "true":
    v = repo.ref
    t = v
    repo.dist_file(CHANGELOG, c)
  elif push == "true":
    print(f"Pushing changes for v{v}")
    repo.publish(t, CHANGELOG, c)    
  save_github_output(n, v, t)
  repo.dist_file('notes.md', n)
  
if __name__ == '__main__':
  parser = argparse.ArgumentParser(
    prog='version-bumper',
    description='A duploctl version bumper.',
  )
  parser.add_argument('--action', type=str, help='The type of version bump to perform.', default="patch")
  parser.add_argument('--push', type=str, help='Push to remote?', default="false")
  parser.add_argument('--token', type=str, help='Github token', default=os.environ.get('GITHUB_TOKEN'))
  args = parser.parse_args()
  publish(**vars(args))
