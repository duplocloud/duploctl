from dataclasses import dataclass
from typing import Any, List, TypeVar, Callable, Type, cast


T = TypeVar("T")


def from_str(x: Any) -> str:
    assert isinstance(x, str)
    return x


def from_int(x: Any) -> int:
    assert isinstance(x, int) and not isinstance(x, bool)
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
class CapacityProviderStrategy:
    capacity_provider: str
    weight: int
    base: int

    @staticmethod
    def from_dict(obj: Any) -> 'CapacityProviderStrategy':
        assert isinstance(obj, dict)
        capacity_provider = from_str(obj.get("capacity_provider"))
        weight = from_int(obj.get("weight"))
        base = from_int(obj.get("base"))
        return CapacityProviderStrategy(capacity_provider, weight, base)

    def to_dict(self) -> dict:
        result: dict = {}
        result["capacity_provider"] = from_str(self.capacity_provider)
        result["weight"] = from_int(self.weight)
        result["base"] = from_int(self.base)
        return result


@dataclass
class UpdateEcsServiceConfig:
    name: str
    task_version: str
    replicas: int
    shared_lb: bool
    dns_prefix: str
    hc_grace_period: int
    old_task_definition_buffer_size: int
    capacity_provider_strategy: List[CapacityProviderStrategy]

    @staticmethod
    def from_dict(obj: Any) -> 'UpdateEcsServiceConfig':
        assert isinstance(obj, dict)
        name = from_str(obj.get("name"))
        task_version = from_str(obj.get("task_version"))
        replicas = from_int(obj.get("replicas"))
        shared_lb = from_bool(obj.get("shared_lb"))
        dns_prefix = from_str(obj.get("dns_prefix"))
        hc_grace_period = from_int(obj.get("hc_grace_period"))
        old_task_definition_buffer_size = from_int(obj.get("old_task_definition_buffer_size"))
        capacity_provider_strategy = from_list(CapacityProviderStrategy.from_dict, obj.get("capacity_provider_strategy"))
        return UpdateEcsServiceConfig(name, task_version, replicas, shared_lb, dns_prefix, hc_grace_period, old_task_definition_buffer_size, capacity_provider_strategy)

    def to_dict(self) -> dict:
        result: dict = {}
        result["name"] = from_str(self.name)
        result["task_version"] = from_str(self.task_version)
        result["replicas"] = from_int(self.replicas)
        result["shared_lb"] = from_bool(self.shared_lb)
        result["dns_prefix"] = from_str(self.dns_prefix)
        result["hc_grace_period"] = from_int(self.hc_grace_period)
        result["old_task_definition_buffer_size"] = from_int(self.old_task_definition_buffer_size)
        result["capacity_provider_strategy"] = from_list(lambda x: to_class(CapacityProviderStrategy, x), self.capacity_provider_strategy)
        return result


def update_ecs_service_config_from_dict(s: Any) -> UpdateEcsServiceConfig:
    return UpdateEcsServiceConfig.from_dict(s)


def update_ecs_service_config_to_dict(x: UpdateEcsServiceConfig) -> Any:
    return to_class(UpdateEcsServiceConfig, x)

