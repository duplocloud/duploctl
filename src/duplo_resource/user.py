from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("user")
class DuploUser(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self.tenent_svc = duplo.load('tenant')

  @Command("ls")
  def list(self):
    """Retrieve a list of all users in the Duplo system."""
    response = self.duplo.get("admin/GetAllUserRoles")
    return response.json()
  
  @Command("get")
  def find(self, 
           name: args.NAME):
    """Find a User by their username."""
    try:
      return [u for u in self.list() if u["Username"] == name][0]
    except IndexError:
      raise DuploError(f"User '{name}' not found", 404)
  
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
    response = self.duplo.post("admin/UpdateUserRole", body)
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
    self.duplo.post("admin/UpdateUserRole", body)
    return {"message": name+ " deleted successfully"}
