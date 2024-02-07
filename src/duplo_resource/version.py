from duplocloud.client import DuploClient
from duplocloud.commander import Resource
from importlib.metadata import version

@Resource("version")
class DuploVersion():
  def __init__(self, duplo: DuploClient):
    self.duplo = duplo
    
  def __call__(self):
    """Get Duplo version.
    
    Returns:
      The Duplo version.
    """
    server = self.duplo.get("build-metadata.json")
    cli = version('duplocloud-client')
    return {
      "cli": cli,
      "ui": server.json()
    }
