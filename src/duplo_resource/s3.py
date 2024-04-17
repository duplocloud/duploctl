from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Resource


@Resource("s3")
class DuploS3(DuploTenantResourceV3):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "aws/s3bucket")

  def name_from_body(self, body):
    return body["Name"]