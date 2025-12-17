from duplocloud.client import DuploClient
from duplocloud.resource import DuploResourceV3
from duplocloud.commander import Resource

@Resource("batch_job", scope="tenant")
class DuploBatchSchedulingPolicy(DuploResourceV3):
  """Manage AWS Batch Scheduling Policies

  Run batch jobs as a managed service on AWS infrastructure. 

  Read more docs here: 
  https://docs.duplocloud.com/docs/overview/aws-services/batch
  """

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, 
                     slug="aws/batchSchedulingPolicy",
                     prefixed=True)

  def name_from_body(self, body):
    return body["Name"]

  