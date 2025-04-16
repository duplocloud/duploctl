from duplocloud import args
from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource

@Resource("aws_secret")
class DuploAwsSecret(DuploTenantResourceV3):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "aws/secret")
  
  def name_from_body(self, body):
    return body["Name"]
  
  @Command()
  def create(self, 
             name: args.NAME=None,
             body: args.BODY=None,
             value: args.PARAM_CONTENT=None,
             dryrun: args.DRYRUN=False,
             wait: args.WAIT=False) -> dict:
    """Create an AWS Secretmanager Secret
    Usage: cli usage
      ```sh
      duploctl aws_secret create <name> -pval <value>
      ```
    
    Args:
      name: The name of the AWS Secret to create.
      -pval/--parametervalue: Arbitrary text to set in the AWS secret.
      -body: path to a raw json/yaml post body, e.g:
      ```
      {
        Name: "test2", 
        SecretString: '{"Foo": "Bar", "Biz":"Baz"}'
      }
      ```

    Returns: 
      resource: The AWS secret object.
      
    Raises:
      DuploError: If the AWS secret already exists.
    """
    # Make sure the user passes name and value, or a body (from file).
    if not body and (not name or not value):
      raise DuploError("name and value are required when body is not provided")
    if not body:
      body = {}
    # If the user passed in settings, use them.  Otherwise use what's in the file.
    if name:
      body['Name'] = name
    if value:
      body['SecretString'] = value
    if dryrun:
      return body
    else:
      return super().create(body, wait=wait)

  @Command()
  #Implement find with opt-in option to display sensitive data. 
  #Note that using find still returns the sensitive data!
  def find(self, 
           name: args.NAME,
           show_sensitive: args.SHOW_SENSITIVE=False) -> dict:
    """Find as AWS Secretmanager secret by name and return it's content

    Usage: cli usage
      ```sh
      duploctl aws_secret find <name>
      ```
    
    Args:
      name: The name of the AWS secret to find.
      -show/--showsensitive: Display value of the secretstring field

    Returns: 
      resource: The AWS secret object.
      
    Raises:
      DuploError: If the AWS secret could not be found.
    """
    response = self.duplo.get(self.endpoint(name))
    if not show_sensitive:
      obfuscated_response=response.json()
      sensitive_len=len(response.json()["SecretString"])
      placeholder="*"
      obfuscated_response["SecretString"]=placeholder * sensitive_len
      return obfuscated_response
    else:
      return response.json()
    
  @Command()
  def update(self, 
             name: args.NAME=None,
             value: args.PARAM_CONTENT=None,
             dryrun: args.DRYRUN=False,
             wait: args.WAIT=False) -> dict:
    """Update an AWS Secretmanager secret.
    Usage: cli usage
      ```sh
      duploctl aws_secret update <name> -pval <newvalue>
      ```
    
    Args:
      name: The name of the AWS secret to find.
      -pval/--parametervalue: The new value for the AWS secret.  This overwrites the existing value!

    Returns: 
      resource: The AWS secret object.
      
    Raises:
      DuploError: If the AWS secret could not be found or doesn't exist.
    """
    body=self.find(name)
    body['SecretString'] = value
    return super().update(name=name, body=body)

  @Command()
  def delete(self,
             name: args.NAME) -> dict:
    """Delete an AWS Secretmanager secret.

    Deletes an AWS Secretmanager secret by name.

    Usage: cli
      ```sh
      duploctl aws_secret delete <name>
      ```

    Args:
      name: The name of an AWS Secretmanager secret to delete.
      wait: Wait for an AWS Secretmanager secret to be deleted.

    Returns:
      message: A success message.
    """
    super().delete(name)
    return {
      "message": f"Successfully deleted secret '{name}'"
    }
