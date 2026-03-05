from duplocloud.controller import DuploCtl
from duplocloud.resource import DuploResourceV3
from duplocloud.commander import Resource


@Resource("s3", scope="tenant")
class DuploS3(DuploResourceV3):
  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo, "aws/s3bucket")

  def name_from_body(self, body):
    return body["Name"]