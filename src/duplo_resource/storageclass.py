from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Resource


@Resource("storageclass")
class DuploStorageClass(DuploTenantResourceV3):
  """
  DuploStorageClass is a resource that represents a Kubernetes StorageClass.  

  See  
   - https://docs.duplocloud.com/docs/overview/aws-services/storage/adding-k8s-storage-class
  """
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "k8s/storageclass")

  def name_from_body(self, body):
    return body["name"]
