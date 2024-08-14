from git import Repo
from packaging.version import Version
import semver
import os
import datetime
from jinja2 import Template

CHANGELOG = 'CHANGELOG.md'
REPO_URL = "https://github.com/duplocloud/duploctl"

class Project:
  def __init__(self):
    self.__latest_tag = None
    self.__changelog = None
    self.cwd = os.getcwd()
    self.repo = Repo(self.cwd)

  @property
  def ref(self):
    return self.repo.head.reference
  
  @property
  def changelog(self):
    if not self.__changelog:
      with open(CHANGELOG, 'r') as f:
        self.__changelog = f.read()
    return self.__changelog
  
  @property
  def latest_tag(self):
    if not self.__latest_tag:
      latest = Version("0.0.0")
      for t in self.repo.tags:
        v = Version(t.name[1:])
        if v > latest:
          latest = v
      self.__latest_tag = semver.VersionInfo.parse(str(latest))
    return self.__latest_tag
  
  def bump_version(self, action: str="patch"):
    latest = self.latest_tag
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

  def release_notes(self, version="Unreleased"):
    header = f"## [{version}]"
    inblock = False
    msg = []
    for line in self.changelog.splitlines():
      if line.startswith(header):
        inblock = True
        continue
      if inblock and line.startswith("## ["):
        break
      if inblock:
        msg.append(line.strip())
    return "\n".join(msg)
  
  def install_notes(self, version):
    # get the install.md file within the wiki folder
    with open("wiki/Installation.md") as f:
      tpl = Template(f.read())
      return tpl.render(version=version, repo_url=REPO_URL)
  
  def reset_changelog(self, version):
    unreleased = "## [Unreleased]"
    # get todays date formatted like 2023-03-05
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    new_notes = f"{unreleased}\n\n## [{version}] - {date}"
    return self.changelog.replace(unreleased, new_notes)
