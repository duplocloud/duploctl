from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV2
from duplocloud.commander import Command, Resource
import duplocloud.args as args

_STATUS_CODES = {
  "1": "Running",
  "3": "Pending",
  "4": "Waiting",
  "6": "Deleted",
  "7": "Failed",
  "11": "Succeeded"
}

@Resource("pod")
class DuploPod(DuploTenantResourceV2):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self.paths = {
      "list": "GetPods"
    }
    self.__last_lines = {}

  @Command()
  def logs(self,
           name: args.NAME = None,
           pod: dict = None):
    """Retrieve logs for a pod."""
    if not pod:
      pod = self.find(name)
    # must be certain status for logs and a host is present
    if pod["CurrentStatus"] not in [1, 11, 7] or not pod["Host"]:
      return None
    id = pod["InstanceId"]
    data = {
      "HostName": pod["Host"],
      "DockerId": pod["Containers"][0]["DockerId"],
      "Tail": 50
    }
    response = self.duplo.post(self.endpoint("findContainerLogs"), data)
    o = response.json()
    lines = o["Data"].split("\n")
    if lines[-1] == "":
      lines.pop()
    last = self.__last_lines.get(id, 0)
    count = len(lines)
    diff = count - last
    self.__last_lines[id] = count
    if diff > 0:
      title = id
      spaces = len(title) * " "
      for line in lines[-diff:]:
        self.duplo.logger.warn(f"{title}: {line}")
        title = spaces
    return None

  def name_from_body(self, body):
    return body["InstanceId"]
