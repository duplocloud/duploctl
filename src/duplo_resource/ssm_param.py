from duplocloud import args
from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource

@Resource("param")
class DuploParam(DuploTenantResourceV3):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "aws/ssmParameter")
  
  def name_from_body(self, body):
    return body["Name"]
  
  @Command()
  def create(self, 
             name: args.NAME=None,
             body: args.BODY=None,
             paramtype: args.SSM_PARAM_TYPE=None,
             value: args.RAW_CONTENT=None,
             dryrun: args.DRYRUN=False,
             wait: args.WAIT=False) -> dict:
    """Create an SSM Parameter"""
    if not body and (not name or not paramtype):
      raise DuploError("name and parameter type are required when body is not provided")
    if not body:
      body = {}
    body['Type'] = paramtype
    # also make sure the data key is present
    if 'Value' not in body:
      body['Value'] = {}
    if name:
      body['Name'] = name
    if value:
      body['Value'] = value
    if dryrun:
      return body
    else:
      return super().create(body, wait=wait)

  @Command()
  #Implement find with opt-in option to display sensitive data for secureString params. 
  #Note that using find on SecureString params still returns the sensitive data!
  #This is only to protect against accidental sensitive data exposure.
  def find(self, 
           name: args.NAME,
           show_sensitive: args.SHOW_SENSITIVE=False) -> dict:
    """Find SSM Parameter resources by name

    Usage: cli usage
      ```sh
      duploctl ssm_param find <name>
      ```
    
    Args:
      name: The name of the SSM Parameter to find.
      -show/--showsensitive: Display value of SecureString parameters

    Returns: 
      resource: The SSM Parameter object.
      
    Raises:
      DuploError: If the SSM Parameter could not be found.
    """
    response = self.duplo.get(self.endpoint(name))
    if response.json()['Type']=="SecureString" and not show_sensitive:
      obfuscated_response=response.json()
      sensitive_len=len(response.json()["Value"])
      placeholder="*"
      obfuscated_response["Value"]=placeholder * sensitive_len
      return obfuscated_response
    else:
      return response.json()
    
  @Command()
  def update(self, 
             strategy: args.STRATEGY,
             name: args.NAME=None,
             value: args.RAW_CONTENT=None,
             dryrun: args.DRYRUN=False,
             wait: args.WAIT=False) -> dict:
    """Update an SSM Parameter."""
    current=self.find(name)
    body=current
    if strategy=='merge' and current['Type']=="StringList":
      current_value = current['Value'].split(',')
      current_value.append(value)
      print(body)
      body['Value'] = ','.join(current_value)
      print(body)
    else:
      body['Value'] = value
    return super().update(body)
