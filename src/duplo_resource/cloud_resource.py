from duplocloud.controller import DuploCtl
from duplocloud.resource import DuploResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("cloud_resource", scope="tenant")
class DuploCloudResource(DuploResource):
    """Retrieve all AWS cloud resources for a tenant.

    Provides access to the unified GetCloudResources endpoint which
    returns all resource types (ECR, Kafka, S3, etc.) in a single
    list. Individual resource types load this resource and filter by
    ResourceType rather than calling this endpoint directly.
    """

    api_version = "v2"

    def __init__(self, duplo: DuploCtl):
        super().__init__(duplo, api_version="v2")

    def endpoint(self, path: str = None):
        """Portal-scoped endpoint, overridden by tenant scope injection."""
        return path

    def name_from_body(self, body):
        """Extract resource name from body."""
        return body.get("Name")

    @Command()
    def list(
        self,
        resource_type: args.RESOURCE_TYPE = None
    ) -> list:
        """List all cloud resources for the tenant.

        Optionally filter by resource type number.

        Usage: CLI Usage
          ```sh
          duploctl cloud_resource list
          duploctl cloud_resource list --type 17
          ```

        Args:
          resource_type: Optional resource type number to filter by.

        Returns:
          list: Cloud resources, optionally filtered by type.
        """
        response = self.duplo.client.get(
            self.endpoint("GetCloudResources")
        )
        resources = response.json()
        if resource_type is not None:
            return [
                r for r in resources
                if r.get("ResourceType") == resource_type
            ]
        return resources

    @Command()
    def find(
        self,
        name: args.NAME,
        resource_type: args.RESOURCE_TYPE = None
    ) -> dict:
        """Find a cloud resource by name.

        Optionally restrict the search to a specific resource type.

        Usage: CLI Usage
          ```sh
          duploctl cloud_resource find <name>
          duploctl cloud_resource find <name> --type 17
          ```

        Args:
          name: The name of the cloud resource to find.
          resource_type: Optional resource type number to filter by.

        Returns:
          resource: The cloud resource object.

        Raises:
          DuploError: If the resource could not be found.
        """
        try:
            return [
                r for r in self.list(resource_type)
                if self.name_from_body(r) == name
            ][0]
        except IndexError:
            raise DuploError(f"Cloud resource '{name}' not found", 404)
