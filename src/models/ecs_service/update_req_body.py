from dataclasses import dataclass
from typing import Any, List, TypeVar, Callable, Type, cast

from models.ecs_service.update_config import (
    UpdateEcsServiceConfig,
    CapacityProviderStrategy,
)

T = TypeVar("T")


def from_int(x: Any) -> int:
    assert isinstance(x, int) and not isinstance(x, bool)
    return x


def from_str(x: Any) -> str:
    assert isinstance(x, str)
    return x


def from_bool(x: Any) -> bool:
    assert isinstance(x, bool)
    return x


def from_list(f: Callable[[Any], T], x: Any) -> List[T]:
    assert isinstance(x, list)
    return [f(y) for y in x]


def to_class(c: Type[T], x: Any) -> dict:
    assert isinstance(x, c)
    return cast(Any, x).to_dict()


@dataclass
class UpdateEcsServiceRequestBody:
    name: str
    task_definition: str
    replicas: int
    dns_prfx: str
    is_target_group_only: bool
    health_check_grace_period_seconds: int
    lb_configurations: List[Any]
    old_task_definition_buffer_size: int
    capacity_provider_strategy: List[CapacityProviderStrategy]
    index: int
    use_index_for_lb: bool
    handle_lb_config_update: bool

    @staticmethod
    def from_config(config: UpdateEcsServiceConfig) -> "UpdateEcsServiceRequestBody":
        return UpdateEcsServiceRequestBody(
            name=config.name,
            task_definition=config.task_version,
            replicas=config.replicas,
            handle_lb_config_update=config.shared_lb,
            dns_prfx=config.dns_prefix,
            health_check_grace_period_seconds=config.hc_grace_period,
            old_task_definition_buffer_size=config.old_task_definition_buffer_size,
            capacity_provider_strategy=config.capacity_provider_strategy,

            # I'm not sure where these values come from...
            lb_configurations=[],
            use_index_for_lb=True,
            is_target_group_only=False,
            index=10,
        )

    @staticmethod
    def from_dict(obj: Any) -> "UpdateEcsServiceRequestBody":
        assert isinstance(obj, dict)
        name = from_str(obj.get("Name"))
        task_definition = from_str(obj.get("TaskDefinition"))
        replicas = from_int(obj.get("Replicas"))
        dns_prfx = from_str(obj.get("DnsPrfx"))
        is_target_group_only = from_bool(obj.get("IsTargetGroupOnly"))
        health_check_grace_period_seconds = from_int(
            obj.get("HealthCheckGracePeriodSeconds")
        )
        lb_configurations = from_list(lambda x: x, obj.get("LBConfigurations"))
        old_task_definition_buffer_size = from_int(
            obj.get("OldTaskDefinitionBufferSize")
        )
        capacity_provider_strategy = from_list(
            CapacityProviderStrategy.from_dict, obj.get("CapacityProviderStrategy")
        )
        index = from_int(obj.get("Index"))
        use_index_for_lb = from_bool(obj.get("UseIndexForLb"))
        handle_lb_config_update = from_bool(obj.get("HandleLbConfigUpdate"))
        return UpdateEcsServiceRequestBody(
            name,
            task_definition,
            replicas,
            dns_prfx,
            is_target_group_only,
            health_check_grace_period_seconds,
            lb_configurations,
            old_task_definition_buffer_size,
            capacity_provider_strategy,
            index,
            use_index_for_lb,
            handle_lb_config_update,
        )

    def to_dict(self) -> dict:
        result: dict = {}
        result["Name"] = from_str(self.name)
        result["TaskDefinition"] = from_str(self.task_definition)
        result["Replicas"] = from_int(self.replicas)
        result["DnsPrfx"] = from_str(self.dns_prfx)
        result["IsTargetGroupOnly"] = from_bool(self.is_target_group_only)
        result["HealthCheckGracePeriodSeconds"] = from_int(
            self.health_check_grace_period_seconds
        )
        result["LBConfigurations"] = from_list(lambda x: x, self.lb_configurations)
        result["OldTaskDefinitionBufferSize"] = from_int(
            self.old_task_definition_buffer_size
        )
        result["CapacityProviderStrategy"] = from_list(
            lambda x: to_class(CapacityProviderStrategy, x),
            self.capacity_provider_strategy,
        )
        result["Index"] = from_int(self.index)
        result["UseIndexForLb"] = from_bool(self.use_index_for_lb)
        result["HandleLbConfigUpdate"] = from_bool(self.handle_lb_config_update)
        return result


def update_ecs_service_request_body_from_dict(s: Any) -> UpdateEcsServiceRequestBody:
    return UpdateEcsServiceRequestBody.from_dict(s)


def update_ecs_service_request_body_to_dict(x: UpdateEcsServiceRequestBody) -> Any:
    return to_class(UpdateEcsServiceRequestBody, x)
