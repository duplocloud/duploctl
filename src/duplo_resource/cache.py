from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource


@Resource("cache")
class DuploCache(DuploResource):
  """Duplo Cache Resource

  Manage the local duploctl credential and cooldown cache.

  Usage: Basic CLI Use
    ```sh
    duploctl cache <action>
    ```
  """

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)

  @Command()
  def clear(self) -> dict:
    """Clear all cached credentials and cooldown files.

    Usage: CLI Usage
      ```sh
      duploctl cache clear
      ```

    Returns:
      message: Summary of cleared files.
    """
    count = self.duplo.clear_cache()
    return {"message": f"Cleared {count} cached file(s)"}
