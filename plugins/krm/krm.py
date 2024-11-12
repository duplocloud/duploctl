from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResource
from duplocloud.commander import Resource, Command
import duplocloud.args as args
from . import common as c

@Resource("krm")
class DuploKRM(DuploResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    
  @Command("apply")
  def apply(self):
    """Apply a KRM File"""
    krm = c.krm_init()
    for item in krm["items"]:
      kind = item["kind"].lower()
      svc = self.duplo.load(kind)
      body = svc.from_krm(item)
      svc.apply(body)
    return krm
