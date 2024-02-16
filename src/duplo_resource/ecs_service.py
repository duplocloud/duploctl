from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args


@Resource("ecs_service")
class DuplEcsService(DuploTenantResource):

    def __init__(self, duplo: DuploClient):
        super().__init__(duplo)

    @Command()
    def list(self):
        """Retrieve a list of all ECS services in a tenant."""
        tenant_id = self.tenant["TenantId"]
        response = self.duplo.get(f"subscriptions/{tenant_id}/aws/ecs/service")
        return response.json()

    @Command()
    def find(self, name: args.NAME):
        """Find a ECS service by name.

        Args:
          name (str): The name of the ECS service to find.
        Returns:
          The ECS service object.
        Raises:
          DuploError: If the ECS service could not be found.
        """

        try:
            return [s for s in self.list() if s["Name"] == name][0]
        except IndexError:
            raise DuploError(f"ECS Service '{name}' not found", 404)

    @Command()
    def update_image(self, name: args.NAME, image: args.IMAGE):
        """Update the image of a ECS service.

        Args:
          name (str): The name of the ECS service to update.
          image (str): The new image to use for the ECS service.
        """
        tenant_id = self.tenant["TenantId"]
        service = self.find(name)
        current_image = None
        for container in service["Template"]["Containers"]:
            if container["Name"] == name:
                current_image = container["Image"]
        if current_image == image:
            self.duplo.post(f"subscriptions/{tenant_id}/UpdateEcsService/{name}")
        else:
            data = {
                "Name": name,
                "Image": image,
                "AllocationTags": service["Template"]["AllocationTags"],
            }
            self.duplo.post(f"subscriptions/{tenant_id}/UpdateEcsService", data)
        return {"message": f"Successfully updated image for ESC service '{name}'"}
