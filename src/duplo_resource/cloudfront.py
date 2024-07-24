from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("cloudfront")
class CloudFront(DuploTenantResourceV3):

    def __init__(self, duplo: DuploClient):
        super().__init__(duplo, "aws/cloudfront")
        self.wait_timeout = 1200

    @Command()
    def create(self, body: args.BODY):
        """Create a CloudFront distribution.
        
        Args:
          body (dict): The body of the request.
        """
        response = self.duplo.post(self.endpoint, body)
        return response.json()

    @Command()
    def list(self):
        """List CloudFront distributions."""
        response = self.duplo.get(self.endpoint)
        return response.json()

    @Command()
    def disable(self, distribution_id: args.NAME):
        """Disable a CloudFront distribution.
        
        Args:
          distribution_id (str): The ID of the distribution to disable.
        """
        body = {"Status": "Disabled"}
        response = self.duplo.put(self.endpoint(distribution_id, "update"), body)
        return response.json()

    @Command()
    def delete(self, distribution_id: args.NAME):
        """Delete a CloudFront distribution.
        
        Args:
          distribution_id (str): The ID of the distribution to delete.
        """
        self.duplo.delete(self.endpoint(distribution_id))
        return {"message": f"CloudFront distribution {distribution_id} deleted"}
