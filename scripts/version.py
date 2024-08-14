#!/usr/bin/env python3
import argparse
import sys
import os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(HERE))
from gha import GithubRepo
from project import Project

def save_github_output(version, tag):
  """Save the tag and version in github output file"""
  outputs = os.environ.get('GITHUB_OUTPUT', './.github/output')
  with open(outputs, 'a') as f:
    f.write(f"version={version}\n")
    f.write(f"tag={tag}\n")

def publish(action, push, token):
  gha = GithubRepo(token)
  project = Project()
  t = project.latest_tag
  pr_notes = gha.generate_release_notes(str(t), "v0.2.32")
  cl_notes = project.release_notes(str(t))
  print(pr_notes["body"])
  # v = project.bump_version(action)
  # t = f"v{v}"
  # c = get_changelog()
  # n = release_notes(c)
  # c = replace_unreleased(c, v)
  # if push != "true":
  #   v = repo.ref
  #   t = v
  #   repo.dist_file(CHANGELOG, c)
  # elif push == "true":
  #   print(f"Pushing changes for v{v}")
  #   repo.publish(t, CHANGELOG, c)    
  # save_github_output(n, v, t)
  # repo.dist_file('notes.md', n)
  
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
