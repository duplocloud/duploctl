
import yaml
from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResource
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args
from models.ecs_service.update_req_body import UpdateEcsServiceRequestBody, CapacityProviderStrategy
from models.ecs_service.update_config import UpdateEcsServiceConfig


@Resource("ecs_service")
class DuploEcsService(DuploTenantResource):

    def __init__(self, duplo: DuploClient):
        super().__init__(duplo)

    @Command()
    def list(self):
        """Retrieve a list of all ECS services in a tenant."""
        tenant_id = self.tenant["TenantId"]
        url = f"v3/subscriptions/{tenant_id}/aws/ecs/service"
        response = self.duplo.get(url)
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
            return [s for s in self.list() if s["DuploEcsService"]["Name"] == name][0]
        except IndexError:
            raise DuploError(f"ECS Service '{name}' not found", 404)

    @Command()
    def update(
        self,
        config_fp:args.FILE,
    ):
        """Update an ECS image

        Args:
            config_fp (str): The path to the update config file.
        Returns:
            A message indicating the success of the operation.
        Raises:
            DuploError: If the config file is not found or is invalid."""
        try:
            with open(config_fp, 'r') as f:
                data = yaml.safe_load(f)
                config = UpdateEcsServiceConfig(**data)
                body = UpdateEcsServiceRequestBody.from_config(config)
        except FileNotFoundError:
            raise DuploError(f"File '{config_fp}' not found", 404)
        except yaml.YAMLError:
            raise DuploError(f"Invalid YAML file '{config_fp}'", 400)


        tenant_id = self.tenant["TenantId"]

        self.duplo.post(
            f"subscriptions/{tenant_id}/UpdateEcsService",
            UpdateEcsServiceRequestBody.to_dict(body)
        )

        return {
            "message": f"Successfully updated image for ECS service '{config.name}'"
        }

    @Command()
    def create_update_config(self, dest_fp: args.FILE):
        """Create a sample update config file for ECS service.

        Args:
          dest_fp (str): The file path to write the config to.
        Returns:
          The path to the created file.
        """
        config = UpdateEcsServiceConfig(
            name="ecs-service-name",
            task_version="task-def-version",
            replicas=1,
            shared_lb=True,
            dns_prefix="dns-prefix",
            hc_grace_period=300,
            old_task_definition_buffer_size=2,
            capacity_provider_strategy=[
                CapacityProviderStrategy(
                    capacity_provider="capacity-provider-name",
                    weight=1,
                    base=1
                )
            ]
        )
        with open(dest_fp, 'w') as f:
            yaml.dump(UpdateEcsServiceConfig.to_dict(config), f)
        return dest_fp
