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
    version (dict): The Duplo version.
  """
  def __init__(self, duplo: DuploClient):
    self.duplo = duplo
    
  def __call__(self) -> dict:
    ui = None
    server = None
    v = {
      "cli": version('duplocloud-client')
    }
    try:
      ui = self.duplo.get("build-metadata.json")
      server = self.duplo.get("v3/version")
    except Exception:
      pass
    finally:
      if ui:
        v["ui"] = ui.json()
      if server:
        v["server"] = server.json()
    return v
