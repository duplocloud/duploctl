from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
from importlib.metadata import version

@Resource("jit")
class DuploVersion(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    
  def __call__(self):
    """Get Duplo version.
    
    Returns:
      The Duplo version.
    """
    server = self.duplo.get("build-metadata.json")
    cli = version('duplocloud-client')
    return {
      "cli": cli,
      "server": server
    }

