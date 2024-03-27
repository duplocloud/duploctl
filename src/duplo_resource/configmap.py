from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Resource

@Resource("configmap")
class DuploConfigMap(DuploTenantResourceV3):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "k8s/configmap")

