from duplocloud.controller import DuploCtl
from duplocloud.resource import DuploResourceV3
from duplocloud.commander import Resource


@Resource("pvc", scope="tenant")
class PersistentVolumeClaim(DuploResourceV3):
  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo, "k8s/pvc")

  def name_from_body(self, body):
    return body["name"]