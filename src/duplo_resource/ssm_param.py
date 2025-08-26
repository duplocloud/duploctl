from duplocloud import args
from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource

@Resource("ssm_param")
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
             value: args.CONTENT=None,
             dryrun: args.DRYRUN=False) -> dict:
    """Create an SSM Parameter
    Usage: cli usage
      ```sh
      duploctl ssm_param create <name> -pval <value> -ptype <String|SecureString|StringList>
      ```
    
    Args:
      name: The name of the SSM Parameter to create.
      -ptype/--parametertype: The type of parameter to create, must be String, SecureString, or StringList
      -pval/--parametervalue: Arbitrary text to set in the parameter.  StringList expects comma separated values.
      -body: path to a raw json/yaml post body, e.g:
      ```
      {
        "Type": "String",
        "Value": "myvalue",
        "Name": "MyStringParameter"
      }
      ```

    Returns: 
      resource: The SSM Parameter object.
      
    Raises:
      DuploError: If the SSM Parameter already exists.
    """
    # Make sure the user passes name and value, or a body (from file). Paramtype is defaulted to string.
    if not body and (not name or not value):
      raise DuploError("name and parameter value are required when body is not provided")
    if not body:
      body = {}
    # If the user passed in settings, use them.  Otherwise use what's in the file.
    if paramtype:
      body['Type'] = paramtype
    if name:
      body['Name'] = name
    if value:
      body['Value'] = value
    if dryrun:
      return body
    else:
      return super().create(body, wait=self.duplo.wait)

  @Command()
  #Implement find with opt-in option to display sensitive data for secureString params. 
  #Note that using find on SecureString params still returns the sensitive data!
  #This is only to protect against accidental sensitive data exposure.
  def find(self, 
           name: args.NAME,
           show_sensitive: args.SHOW_SENSITIVE=False) -> dict:
    """Find SSM Parameter resources by name and return it's content

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
             name: args.NAME=None,
             strategy: args.STRATEGY='merge',
             value: args.CONTENT=None,
             dryrun: args.DRYRUN=False) -> dict:
    """Update an SSM Parameter.
    Usage: cli usage
      ```sh
      duploctl ssm_param update <name> -pval <newvalue>
      ```
    
    Args:
      name: The name of the SSM Parameter to find.
      -strat/--strategy: whether to merge or overwrite StringList Parameters (default is merge, not used for SecureString or String params)
      -pval/--parametervalue: The new value for the SSM Parameter.  Overwrites existing unless merging with StringList parameters.

    Returns: 
      resource: The SSM Parameter object.
      
    Raises:
      DuploError: If the SSM Parameter could not be found or doesn't exist.
    """
    body=self.find(name)
    if strategy=='merge' and body['Type']=="StringList":
      current_value = body['Value'].split(',')
      current_value.append(value)
      body['Value'] = ','.join(current_value)
    else:
      body['Value'] = value
    return super().update(name=name, body=body)
