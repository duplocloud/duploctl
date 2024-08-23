from duplocloud import args
from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource

@Resource("secret")
class DuploSecret(DuploTenantResourceV3):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "k8s/secret")

  def name_from_body(self, body):
    return body["SecretName"]
  
  @Command()
  def create(self, 
             name: args.NAME=None,
             body: args.BODY=None,
             data: args.DATAMAP=None,
             dryrun: args.DRYRUN=False,
             wait: args.WAIT=False) -> dict:
    """Create a Secret"""
    if not name and not body:
      raise DuploError("Name is required when body is not provided")
    if not body:
      body = {}
    # also make sure the data key is present
    if 'SecretData' not in body:
      body['SecretData'] = {}
    if name:
      body['SecretName'] = name
    if data:
      body['SecretData'].update(data)
    if dryrun:
      return body
    else:
      return super().create(body, wait=wait)
