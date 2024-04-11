#!/usr/bin/env python3
import datetime
import os
import sys

UNRELEASED = "## [Unreleased]"
CHANGELOG = os.path.join(os.path.dirname(__file__), '../CHANGELOG.md')

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
      msg.append(line)
  return "\n".join(msg)

def replace_unreleased(changelog, version):
  # get todays date formatted like 2023-03-05
  date = datetime.datetime.now().strftime("%Y-%m-%d")
  new_notes = f"{UNRELEASED}\n\n## [{version}] - {date}"
  return changelog.replace(UNRELEASED, new_notes)
  
def main():
  # get the first arg as the version
  v = sys.argv[1]
  c = get_changelog()
  notes = release_notes(c)
  c = replace_unreleased(c, v)
  save_changelog(c)
  print(notes)
  # print(c)
  
if __name__ == '__main__':
  main()
