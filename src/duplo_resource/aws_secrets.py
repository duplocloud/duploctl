from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("aws_secrets")
class DuploAwsSecrets(DuploTenantResourceV3):
  
  def __init__(self, duplo: DuploClient):
    print("I am here")
    super().__init__(duplo, "aws/secret")
    # self.wait_timeout = 1200
    
