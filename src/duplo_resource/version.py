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
    self.paths = {
      "ui": "build-metadata.json", 
      "frontdoor": "frontdoor/build-metadata.json",
      "backend": "v3/version",
      "auth": "v3/auth/version",
      "katkit": "v3/katkit/version",
      "billing": "v3/billing/version",
      "security": "v3/security/version"
    }
    
  def __call__(self) -> dict:
    v = {}
    # first get cli version then server versions
    v["cli"] = {
      "tag": version('duplocloud-client')
    }
    for (name, path) in self.paths.items():
      try:
        res = self.duplo.get(path).json()
      except Exception as e:
        self.duplo.logger.error(f"Failed to get version for {path}: {e}")
        res = {"error": str(e)}
      finally:
        v[name] = res
    return v
