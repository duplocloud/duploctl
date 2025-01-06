from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV2
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("lambda")
class DuploLambda(DuploTenantResourceV2):
  """Manage Duplo Lambdas
  
  Duplo Lambdas are serverless functions that run in response to events.
  """
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
  
  @Command()
  def list(self) -> list:
    """List Lambdas.

    List all of the tenants in the current tenant.

    Usage: CLI Usage
      ```sh
      duploctl lambda list
      ```
    
    Returns:
      list: A list of all lambdas in the current subscription.
    """
    tenant_id = self.tenant["TenantId"]
    tenant_name = self.tenant["AccountName"]
    response = self.duplo.get(f"subscriptions/{tenant_id}/GetLambdaFunctions")
    if (data := response.json()):
      return data
    else:
      raise DuploError(f"No lambda functions found in tenant '{tenant_name}'", 404)
  
  @Command()
  def find(self, 
           name: args.NAME) -> dict:
    """Find a Lambda function by name.

    Usage: CLI Usage
      ```sh
      duploctl lambda find <name>
      ```
    Args:
      name: The name of the lambda to find.
    Returns: 
      The lambda object.
    Raises:
      DuploError: If the lambda could not be found.
    """
    try:
      return [s for s in self.list() if s["FunctionName"] == name][0]
    except IndexError:
      raise DuploError(f"Lambda '{name}' not found", 404)
    
  @Command()
  def create(self, 
             body: args.BODY,
             wait: args.WAIT = False) -> dict:
    """Create a new tenant.

    Usage: CLI Usage
      ```sh
      duploctl lambda create -f 'lambda.yaml'
      ```
      Contents of the `lambda.yaml` file
      ```yaml
      --8<-- "src/tests/data/lambda.yaml"
      ```
    
    Args:
      body: The lambda body. 
      wait: Whether to wait for the tenant to be created

    Returns:
      message: A success message.
    """
    def wait_check():
      name = self.name_from_body(body)
      self.find(name)
    tenant_id = self.tenant["TenantId"]
    self.duplo.post(f"subscriptions/{tenant_id}/CreateLambdaFunction", body)
    if wait:
      self.wait(wait_check, 400)
    return {
      "message": f"Lambda {body['FunctionName']} created"
    }
  
  @Command()
  def delete(self, 
             name: args.NAME) -> dict:
    """Delete a lambda.

    Usage: CLI Usage
      ```sh
      duploctl lambda delete <name>
      ```
    
    Args:
      name: The name of the lambda to delete.
    
    Returns:
      message: A success message.
    """
    tenant_id = self.tenant["TenantId"]
    self.duplo.post(f"subscriptions/{tenant_id}/DeleteLambdaFunction/{name}")
    return {
      "message": f"Lambda {name} deleted"
    }

  @Command()
  def update_image(self, 
                   name: args.NAME, 
                   image: args.IMAGE) -> dict:
    """Update the image of a lambda.

    Usage: CLI Usage
      ```sh
      duploctl lambda update_image <name> <image>
      ```
    
    Args:
      name: The name of the lambda to update.
      image: The new image to use for the lambda.
    
    Returns:
      message: The updated lambda object
    """
    tenant_id = self.tenant["TenantId"]
    data = {
      "FunctionName": name,
      "ImageUri": image
    }
    response = self.duplo.post(f"subscriptions/{tenant_id}/UpdateLambdaFunction", data)
    return response.json()

  @Command()
  def update_s3(self, 
                name: args.NAME, 
                bucket: args.S3BUCKET,
                key: args.S3KEY) -> dict:
    """Update the s3 bucket and key of a lambda.

    Usage: CLI Usage
      ```sh
      duploctl lambda update_s3 <name> <bucket> <key>
      ```
    
    Args:
      name: The name of the lambda to update.
      bucket: The s3 bucket to use for the lambda.
      key: The s3 key (file path) to use for the lambda.
    """
    tenant_id = self.tenant["TenantId"]
    data = {
      "FunctionName": name,
      "S3Bucket": bucket,
      "S3Key": key
    }
    response = self.duplo.post(f"subscriptions/{tenant_id}/UpdateLambdaFunction", data)
    return response.json()

  def name_from_body(self, body):
    prefix = f"duploservices-{self.tenant['AccountName']}"
    name =  body["FunctionName"]
    if not name.startswith(prefix):
      name = f"{prefix}-{name}"
    return name

  @Command()
  def update_env(self,
               name: args.NAME,
               setvar: args.SETVAR,
               strategy: args.STRATEGY,
               deletevar: args.DELETEVAR) -> dict:
    """Update the environment variables of a lambda. If lambda has no environment variables set, use -strat replace to set new values.
    Usage: Basic CLI Use
      ```sh
      duploctl lambda update_env <lambda-name> --setvar env-key1 env-val1 --setvar env-key2 env-val2 --setvar env-key3 env-val3 -strat merge
    Args:
      name (str): The name of the lambda to update.

      setvar/-V (list): A list of key-value pairs to set as environment variables.

      strategy/strat (str): The merge strategy to use for env vars. Valid options are "merge" or "replace". Default is merge.

      deletevar/-D (list): A list of keys to delete from the environment variables.
    """
    tenant_id = self.tenant["TenantId"]
    # Helper function to format new environment variables
    def new_env_vars(setvar):
        return [{"Name": i[0], "Value": i[1]} for i in setvar]
    # Find the current lambda and its environment variables
    current_lambda = self.find(name)
    currentEnv = current_lambda.get('Environment', {}).get('Variables', {})
    # Convert currentEnv to a list of dicts for easier manipulation
    currentEnvList = [{"Name": k, "Value": v} for k, v in currentEnv.items()]
    if strategy == 'merge':
        # Merge new variables with existing ones
        newEnv = new_env_vars(setvar) if setvar else []
        mergedEnvDict = {env['Name']: env for env in currentEnvList + newEnv}
        mergedEnvList = list(mergedEnvDict.values())
    else:
        # Replace existing variables with new ones
        mergedEnvList = new_env_vars(setvar) if setvar else []
    # Handle deletion of variables
    if deletevar:
        mergedEnvList = [env for env in mergedEnvList if env['Name'] not in deletevar]
    # Convert back to a dictionary for AWS Lambda compatibility
    updatedEnvDict = {env['Name']: env['Value'] for env in mergedEnvList}
    # Construct the payload for updating the lambda
    data = {
        "FunctionName": name,
        "Environment": {
            "Variables": updatedEnvDict
        }
    }
    # Send the update request
    response = self.duplo.post(f"subscriptions/{tenant_id}/UpdateLambdaFunctionConfiguration", data)
    return {"message": f"Successfully updated environment variables for lambda '{name}'"}
