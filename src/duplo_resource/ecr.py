from duplocloud.controller import DuploCtl
from duplocloud.resource import DuploResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args

ECR_RESOURCE_TYPE = 17

@Resource("ecr", scope="tenant")
class DuploECR(DuploResourceV3):
    """Manage AWS ECR Repository resources.

    Provides commands to create, find, list, update, and delete
    Elastic Container Registry (ECR) repositories within a tenant.

    Read more at: https://docs.duplocloud.com/docs/overview/aws-services/ecr
    """

    def __init__(self, duplo: DuploCtl):
        super().__init__(duplo, "aws/ecrRepository")
        self._cloud_resource = self.duplo.load("cloud_resource")

    def name_from_body(self, body):
        """Extract the repository name from a response body."""
        return body.get("Name")

    @Command()
    def list(self) -> list:
        """List all ECR repositories for the tenant.

        Usage: CLI Usage
          ```sh
          duploctl ecr list
          ```

        Returns:
          list: A list of ECR repository objects.
        """
        return self._cloud_resource.list(ECR_RESOURCE_TYPE)

    @Command()
    def find(self, name: args.NAME) -> dict:
        """Find an ECR repository by name.

        Usage: CLI Usage
          ```sh
          duploctl ecr find <name>
          ```

        Args:
          name: The name of the ECR repository to find.

        Returns:
          resource: The ECR repository object.

        Raises:
          DuploError: If the repository could not be found.
        """
        return self._cloud_resource.find(name, ECR_RESOURCE_TYPE)

    @Command()
    def create(self, body: args.BODY) -> dict:
        """Create an ECR repository.

        Usage: CLI Usage
          ```sh
          duploctl ecr create -f ecr.yaml
          ```
          Contents of the `ecr.yaml` file
          ```yaml
          --8<-- "src/tests/data/ecr.yaml"
          ```

        Args:
          body: The repository definition.

        Returns:
          resource: The created ECR repository object.

        Raises:
          DuploError: If the repository could not be created.
        """
        body["ResourceType"] = ECR_RESOURCE_TYPE
        return super().create(body)
