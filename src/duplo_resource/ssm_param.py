from urllib.parse import quote

from duplocloud import args
from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResourceV3
from duplocloud.commander import Command, Resource

@Resource("ssm_param", scope="tenant")
class DuploParam(DuploResourceV3):

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo, "aws/ssmParameter")

  def name_from_body(self, body):
    return body["Name"]

  def _encoded_name(self, name: str) -> str:
    """Double URL-encode an SSM parameter name for the path segment.

    SSM parameter names may contain '/' (hierarchy separator). The portal
    rejects a single-encoded '%2F' in the path, so the name must reach
    the API as '%252F' — matching what the browser UI sends.
    """
    return quote(quote(name, safe=''), safe='')
  
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
      return super().create(body)

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
    response = self.client.get(self.endpoint(self._encoded_name(name)))
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
             name: args.NAME = None,
             body: args.BODY = None,
             patches: args.PATCHES = None,
             strategy: args.STRATEGY = 'merge',
             value: args.CONTENT = None,
             dryrun: args.DRYRUN = False) -> dict:
    """Update an SSM Parameter.

    Supports three invocation styles:

    - CLI style: ``update <name> -pval <newvalue>`` fetches the current
      parameter and overwrites (or merges, for StringList) its value.
    - Body style: ``update(name=..., body=<dict>)`` PUTs the given body
      directly. Used by ``apply``.
    - Patch style: ``update(name=..., patches=[...])`` fetches the
      current body, applies JSON patches, then PUTs.

    Usage: cli usage
      ```sh
      duploctl ssm_param update <name> -pval <newvalue>
      ```

    Args:
      name: The name of the SSM Parameter to find.
      body: The full resource body to PUT (used by apply).
      patches: JSON patches to apply to the current body.
      -strat/--strategy: whether to merge or overwrite StringList Parameters (default is merge, not used for SecureString or String params)
      -pval/--parametervalue: The new value for the SSM Parameter.  Overwrites existing unless merging with StringList parameters.
      dryrun: Return the computed body instead of PUTting it.

    Returns:
      resource: The SSM Parameter object.

    Raises:
      DuploError: If the SSM Parameter could not be found or doesn't exist.
    """
    if not name and not body:
      raise DuploError("Name is required when body is not provided")
    if body is None:
      body = self.find(name)
      if value is not None:
        if strategy == 'merge' and body['Type'] == "StringList":
          current_value = body['Value'].split(',')
          current_value.append(value)
          body['Value'] = ','.join(current_value)
        else:
          body['Value'] = value
    if patches:
      body = self.duplo.jsonpatch(body, patches)
    name = name if name else self.name_from_body(body)
    if dryrun:
      return body
    response = self.client.put(self.endpoint(self._encoded_name(name)), body)
    return response.json()

  @Command()
  def delete(self, name: args.NAME) -> dict:
    """Delete an SSM Parameter by name.

    Usage: cli usage
      ```sh
      duploctl ssm_param delete <name>
      ```

    Args:
      name: The name of the SSM Parameter to delete.

    Returns:
      message: A success message.

    Raises:
      DuploError: If the SSM Parameter could not be deleted.
    """
    self.client.delete(self.endpoint(self._encoded_name(name)))
    return {
      "message": f"{self.slug}/{name} deleted"
    }
