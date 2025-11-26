from duplocloud.client import DuploClient
from duplocloud.resource import DuploResourceV3
from duplocloud.commander import Resource


@Resource("s3", scope="tenant")
class DuploS3(DuploResourceV3):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "aws/s3bucket")

  def name_from_body(self, body):
    return body["Name"]