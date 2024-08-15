#!/usr/bin/env python3
import argparse
import sys
import os
import logging
import importlib.metadata as meta
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(HERE))
from gha import GithubRepo
from project import Project, CHANGELOG

logging.basicConfig(level=logging.INFO)

class Versionizer:
  def __init__(self, action, token=None):
    self.logger = logging.getLogger('versionizer')
    self.gha = GithubRepo(token)
    self.project = Project()
    self.last_version = str(self.project.latest_tag)
    self.ref = str(self.project.ref)
    self.action = action
    self.pushed = False
    self.changelog = None
    self.notes = None
    self.__next_version = None

  @property 
  def next_version(self):
    if not self.__next_version:
      self.__next_version = str(self.project.bump_version(self.action))
    return self.__next_version

  def build_release_notes(self, save=True):
    self.logger.info("Building release notes")
    v = self.next_version
    lv = self.last_version
    cl_notes = self.project.release_notes()
    pr_notes = self.gha.generate_release_notes(f"v{v}", f"v{lv}", self.ref)
    inst_notes = self.project.install_notes(v)
    notes = "\n".join([
      cl_notes, 
      pr_notes["body"], 
      "\n## Installation",
      inst_notes])
    if save:
      self.project.dist_file('notes.md', notes)
    self.notes = notes
  
  def reset_changelog(self, save=True):
    self.logger.info(f"Resetting changelog")
    c = self.project.reset_changelog(self.next_version)
    if save:
      self.project.dist_file(CHANGELOG, c)
    self.changelog = c

  def publish(self):
    if not self.pushed:
      self.logger.info(f"Publishing new version {self.next_version}")
      self.gha.publish(f"v{self.next_version}", CHANGELOG, self.changelog)
      self.pushed = True

  def save_github_output(self):
    """Save the tag and version in github output file"""
    tag = f"v{self.next_version}" if self.pushed else self.ref
    version = self.next_version if self.pushed else meta.version('duplocloud-client')
    outputs = os.environ.get('GITHUB_OUTPUT', './.github/output')
    self.logger.info(f"Saving Outputs: tag={tag} version={version}")
    with open(outputs, 'a') as f:
      f.write(f"tag={tag}\n")
      f.write(f"version={version}\n")

if __name__ == '__main__':
  parser = argparse.ArgumentParser(
    prog='version-bumper',
    description='A duploctl version bumper.',
  )
  parser.add_argument('--action', 
                      type=str, 
                      help='The type of version bump to perform.', 
                      choices=['major', 'minor', 'patch'], 
                      default="patch")
  parser.add_argument('--push', 
                      type=str, 
                      help='Push to remote?', 
                      default="false")
  parser.add_argument('--token', 
                      type=str, 
                      help='Github token', 
                      default=os.getenv('GITHUB_TOKEN', None))
  args = parser.parse_args()
  v = Versionizer(args.action, args.token)
  v.build_release_notes()
  v.reset_changelog()
  if args.push == "true":
    v.publish()
  v.save_github_output()
