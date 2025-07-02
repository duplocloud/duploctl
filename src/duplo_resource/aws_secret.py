from duplocloud import args
from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import json

@Resource("aws_secret")
class DuploAwsSecret(DuploTenantResourceV3):
  """AWS Secrets Manager Secrets resource.

  This resource allows you to create, find, update, and delete AWS Secrets Manager secrets.

  Usage:
    ```sh
    duploctl aws_secret <cmd> [options]
    ```

  Manages [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/) in the background. 
  """
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "aws/secret")
  
  def name_from_body(self, body):
    return body.get("Name", None)
  
  @Command()
  #Implement find with opt-in option to display sensitive data. 
  #Note that using find still returns the sensitive data!
  def find(self, 
           name: args.NAME,
           show_sensitive: args.SHOW_SENSITIVE=False) -> dict:
    """Find as AWS Secretmanager secret by name and return its content

    Usage: cli usage
      ```sh
      duploctl aws_secret find <name>
      ```
    
    Args:
      name: The name of the AWS secret to find.
      show_sensitive: Display value of the secretstring field

    Returns: 
      resource: The AWS secret object.
      
    Raises:
      DuploError: If the AWS secret could not be found.
    """
    # if the name has the prefix we good, otherwise add it
    response = None
    try:
      response = self.duplo.get(self.endpoint(name))
    except DuploError as e:
      # if it wasn't found try with the full prefix
      if e.code == 400:
        response = self.duplo.get(self.endpoint(self._prefix_name(name)))
      else:
        raise e
    if not show_sensitive:
      obfuscated_response = response.json()
      sensitive_len = len(response.json()["SecretString"])
      placeholder = "*"
      obfuscated_response["SecretString"] = placeholder * sensitive_len
      return obfuscated_response
    else:
      return response.json()
  
  @Command()
  def create(self, 
             name: args.NAME=None,
             body: args.BODY=None,
             data: args.DATAMAP=None,
             value: args.CONTENT=None,
             dryrun: args.DRYRUN=False) -> dict:
    """Create an AWS Secretmanager Secret

    Using DuploCloud's native support for AWS Secrets Manager, you can create a new secret. This method acts and feels like how the Kubernetes secrets work within this cli. Supports the secrets value as a string or a key/value JSON object where each value is a string. If you give a JSON object with any key that is not a string, the entire value will be simply a string with a JSON value. The examples below mostly include the `--dry-run` so you can see the output. Simply remove that to actually create the secret.

    Usage: cli usage
      ```sh
      duploctl aws_secret create <name> <args>
      ```

    Example: Create a secret from a datamap
      ```sh
      duploctl aws_secret create mysecret --from-literal foo=bar --from-file some-config.json
      ```

    Example: Create a secret with a value
      ```sh
      duploctl aws_secret create mysecret --value foobarbaz
      ```

    Example: Merge a body with new keys
      Notice the the `--file` flag is set to `-` which means it will read a body file from stdin. Since a name is given, the name in the body file will be replaced with the name given in the command.
      ```sh
      cat awssecret.yaml | duploctl aws_secret create mysecret --file - --from-file some-config.json --from-literal icecream=vanilla --dry-run 
      ```
      Here is what the file body within awssecret.yaml looks like
      ```yaml
      --8<-- "src/tests/data/awssecret.yaml"
      ```
      And then the some-config.json file looks like this
      ```json
      --8<-- "src/tests/files/some-config.json"
      ```
      
    Args:
      name: The name of the AWS Secret to create.
      body: The full body of an AWS Secrets Manager secret for DuploCloud.
      data: A map of key-value pairs to be merged into the SecretString field of the AWS Secretmanager secret. Can't be used with the value argument. A datamap is a combination of all of the `--from-literal` and `--from-file` flags.
      value: The value of the AWS Secretmanager secret. This overwrites the existing value! Can't be used with the data argument.
      dryrun: If true, returns the body that would be sent to the API without actually creating the resource.

    Returns: 
      message: Either a succes message is returned or if --dry-run is passed then the body is what is returned. 
      
    Raises:
      DuploError: If the AWS secret already exists.
    """
    # Make sure the user passes name and value, or a body (from file).
    if not name and not body:
      raise DuploError("Name is required when body is not provided")
    if value and data: 
      raise DuploError("You cannot use --value with --from-file or --from-literal. Use one or the other.")
    if not body:
      body = {}
    # If the user passed in a name then this takes precedence over the body name.
    if name:
      body['Name'] = name
    if value:
      body['SecretString'] = value
    elif data:
      # if we have data, then we need to parse the SecretString as json so we can merge the data into it
      secretString = body.get('SecretString', '{}')
      body['SecretString'] = self._merge_data(secretString, data)
    if dryrun:
      return body
    else:
      return super().create(body=body)
    
  @Command()
  def update(self, 
             name: args.NAME=None,
             body: args.BODY=None,
             data: args.DATAMAP=None,
             value: args.CONTENT=None,
             dryrun: args.DRYRUN=False) -> dict:
    """Update an AWS Secretmanager secret.

    Follows all the same arguments and style of the create method. This requires the secret to already exist. 

    Usage: cli usage
      ```sh
      duploctl aws_secret update <name> <args>
      ```
    
    Args:
      name: The name of the AWS Secret to create.
      body: The full body of an AWS Secrets Manager secret for DuploCloud.
      data: A map of key-value pairs to be merged into the SecretString field of the AWS Secrets Manager secret. Cannot be used with the value argument. A datamap is a combination of all of the `--from-literal` and `--from-file` flags.
      value: The value of the AWS Secrets Manager secret. OVERWRITES the existing value. Cannot be used with the data argument.
      dryrun: If true, returns the body that would be sent to the API without actually creating the resource.

    Returns: 
      message: Either a succes message is returned or if --dry-run is passed then the body is what is returned. 
      
    Raises:
      DuploError: If the AWS secret could not be found or doesn't exist.
    """
    if not name and not body:
      raise DuploError("Name is required when body is not provided")
    if value and data: 
      raise DuploError("You cannot pass both value and data. Use one or the other.")
    if not body:
      body = {}
    # If the user passed in a name then this takes precedence over the body name.
    if not name:
      name = self.name_from_body(body)
      if not name:
        raise DuploError("Name is required when the body does not have a name")
    else:
      body['Name'] = name
    # even if we don't use this, it confirms the secret exists before we try and update it
    current = self.find(name, True)
    if value:
      body['SecretString'] = value
    elif data:
      # start with the data from the secret we found
      secretString = current.get('SecretString', '{}')
      body['SecretString'] = self._merge_data(secretString, data)
    body['SecretValueType'] = "plain"
    if dryrun:
      return body
    else:
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
      name: The name of an AWS Secretmanager secret to delete. This can either be the short name or the full name including the tenant prefix.
      wait: Wait for an AWS Secretmanager secret to be deleted.

    Returns:
      message: A success message.
    """
    # if the name has the prefix we good, otherwise add it
    try:
      super().delete(name)
    except DuploError as e:
      # if it wasn't found try with the full prefix
      if e.code == 404:
        super().delete(self._prefix_name(name))
      else:
        raise e
    return {
      "message": f"Successfully deleted secret '{name}'"
    }
  
  def _merge_data(self, secretString: str, data: dict) -> dict: 
    try:
      secretData = json.loads(secretString)
    except json.JSONDecodeError:
      raise DuploError("Unable to parse the secret string to json. To use --from-file or --from-literal, the SecretString must be a valid JSON object encoded as a string where each key and value is a string.")
    # all of the values in the dict must be a string or we need to throw an error
    if not all(isinstance(v, str) for v in secretData.values()):
      raise DuploError("All values in the existing json object must be strings to use --from-file or --from-literal")
    # now let's merge and set this puppy, woof
    secretData.update(data)
    return json.dumps(secretData)

  # adds the prefix only if the name does not start with a slash
  def _prefix_name(self, name: str) -> str:
    dashed = "" if name.startswith("/") else "-"
    return f"duploservices-{self.duplo.tenant}{dashed}{name}"
