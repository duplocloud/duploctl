from duplocloud.client import DuploClient
from duplocloud.commander import Resource
from importlib.metadata import version

@Resource("version")
class DuploVersion():
  """Show Version

  Prints the version of the Duplo CLI, UI, and Server.

  Usage:
    ```sh
    duploctl version
    ```
  
  Returns:
    version: The Duplo version.
  """
  def __init__(self, duplo: DuploClient):
    self.duplo = duplo
    
  def __call__(self) -> dict:
    cli = version('duplocloud-client')
    ui = self.duplo.get("build-metadata.json")
    server = self.duplo.get("v3/version")
    return {
      "cli": cli,
      "ui": ui.json(),
      "server": server.json()
    }
