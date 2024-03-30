from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.commander import Resource

@Resource("configmap")
class DuploAWS(DuploResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)

  def __call__(self, *args):
    return {
      "message": "Hello from AWS plugin!"
    }

