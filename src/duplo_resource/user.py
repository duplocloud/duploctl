from duplocloud.controller import DuploCtl
from duplocloud.resource import DuploResourceV2
from duplocloud.errors import DuploNotFound
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("user")
class DuploUser(DuploResourceV2):
  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)
    self.tenent_svc = duplo.load('tenant')

  def name_from_body(self, body):
    return body["Username"]

  @Command()
  def apply(self,
            body: args.BODY,
            wait: args.WAIT = False) -> dict:
    """Apply a user.

    Usage: CLI Usage
      ```sh
      duploctl user apply -f 'user.yaml'
      ```
      Contents of the `user.yaml` file
      ```yaml
      --8<-- "src/tests/data/user.yaml"
      ```

    Args:
      body: The user body.
      wait: Wait for the user to be applied.

    Returns:
      message: A success message.
    """
    name = self.name_from_body(body)
    try:
      self.find(name)
      if 'State' not in body:
        body['State'] = 'updated'
    except DuploNotFound:
      if 'State' not in body:
        body['State'] = 'added'
    response = self.client.post("admin/UpdateUserRole", body)
    return response.json()

  @Command("ls")
  def list(self):
    """Retrieve a list of all users in the Duplo system."""
    response = self.client.get("admin/GetAllUserRoles")
    return response.json()
  
  @Command("get")
  def find(self, 
           name: args.NAME):
    """Find a User by their username."""
    try:
      return [u for u in self.list() if u["Username"] == name][0]
    except IndexError:
      raise DuploNotFound(name, "User")
  
  @Command()
  def create(self, 
             body: args.BODY) -> dict:
    """Create a new user.

    Usage: CLI Usage
      ```sh
      duploctl user create -f 'user.yaml'
      ```
      Contents of the `user.yaml` file
      ```yaml
      --8<-- "src/tests/data/user.yaml"
      ```
    
    Args:
      body: The user body. 

    Returns:
      message: A success message.
    """
    if 'State' not in body:
      body['State'] = 'added'
    response = self.client.post("admin/UpdateUserRole", body)
    return response.json()
  
  @Command()
  def delete(self, 
             name: args.NAME) -> dict:
    """Delete a User.
    
    Usage: CLI Usage
      ```sh
      duploctl user delete <name>
      ```
    
    Args:
      name: The name of the user to delete.
    
    Returns:
      message: A success message.
    """
    body = {
      "Username": name,
      "State": "deleted"
    }
    self.client.post("admin/UpdateUserRole", body)
    return {"message": name+ " deleted successfully"}
