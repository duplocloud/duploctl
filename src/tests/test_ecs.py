import pytest
from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError
from .conftest import get_test_data

# Shared image used across both task definitions.
# Two families are registered from the same base image with different Commands,
# proving that two independent task def families can coexist in one tenant.
_BASE_IMAGE = "public.ecr.aws/nginx/nginx:stable-alpine"
_UPDATED_IMAGE = "public.ecr.aws/nginx/nginx:mainline-alpine"


@pytest.fixture(scope="class")
def ecs_resource(duplo: DuploCtl):
    resource = duplo.load("ecs")
    resource.duplo.wait = False  # wait toggled per-test where needed
    return resource


def execute_test(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")


@pytest.mark.integration
@pytest.mark.ecs
@pytest.mark.usefixtures("ecs_resource")
class TestEcs:
    """ECS service + task definition integration tests.

    Ordering:
      30  register service task def
      31  register task task def
      32  list / find task def families
      33  create ECS service
      34  find ECS service
      35  update_image (service family) — wait enabled; soft-fail on wait errors
      36  run_task (task family)
      37  list_tasks (task family)
      995 delete ECS service
      996 (no taskdef delete — deregistration not exposed, families GC'd by AWS)
    """

    svc_family = "duploctl-svc"
    task_family = "duploctl-task"

    # ── Task definition registration ─────────────────────────────────────────

    @pytest.mark.dependency(name="register_svc_taskdef", depends=["create_tenant"], scope="session")
    @pytest.mark.order(30)
    def test_register_svc_taskdef(self, ecs_resource):
        """Register the service task definition family."""
        body = get_test_data("ecs-taskdef-service")
        result = execute_test(ecs_resource.update_taskdef, body)
        assert result is not None
        assert "arn" in result
        print(f"Service taskdef ARN: {result['arn']}")

    @pytest.mark.dependency(name="register_task_taskdef", depends=["create_tenant"], scope="session")
    @pytest.mark.order(31)
    def test_register_task_taskdef(self, ecs_resource):
        """Register the standalone task definition family (different Command, same image)."""
        body = get_test_data("ecs-taskdef-task")
        result = execute_test(ecs_resource.update_taskdef, body)
        assert result is not None
        assert "arn" in result
        print(f"Task taskdef ARN: {result['arn']}")

    # ── Task definition find ──────────────────────────────────────────────────

    @pytest.mark.dependency(depends=["register_svc_taskdef", "register_task_taskdef"], scope="session")
    @pytest.mark.order(32)
    def test_find_taskdef_families(self, ecs_resource):
        """List all families and find each by name."""
        families = execute_test(ecs_resource.list_task_def_family)
        assert isinstance(families, list)
        names = [f.get("FamilyName", f.get("Name", f.get("Family", ""))) for f in families]
        # Both prefixed family names should be present
        svc = ecs_resource.prefixed_name(self.svc_family)
        task = ecs_resource.prefixed_name(self.task_family)
        assert any(svc in n for n in names), f"Service family '{svc}' not in list: {names}"
        assert any(task in n for n in names), f"Task family '{task}' not in list: {names}"

        # find_def should return the latest revision for each
        svc_def = execute_test(ecs_resource.find_def, self.svc_family)
        assert svc_def["ContainerDefinitions"][0]["Image"] == _BASE_IMAGE

        task_def = execute_test(ecs_resource.find_def, self.task_family)
        cmd = task_def["ContainerDefinitions"][0].get("Command", [])
        assert "echo hello from duploctl task" in " ".join(cmd)

    # ── ECS service create / find ─────────────────────────────────────────────

    @pytest.mark.dependency(name="create_ecs_service", depends=["register_svc_taskdef"], scope="session")
    @pytest.mark.order(33)
    def test_create_ecs_service(self, ecs_resource):
        """Create an ECS service backed by the service task definition."""
        prefixed = ecs_resource.prefixed_name(self.svc_family)
        try:
            existing = ecs_resource.find_service_family(prefixed)
            if existing:
                print(f"ECS service '{prefixed}' already exists")
                return
        except DuploError:
            pass
        svc_def = execute_test(ecs_resource.find_def, self.svc_family)
        body = get_test_data("ecs-service")
        body["TaskDefinition"] = svc_def["TaskDefinitionArn"]
        body["Name"] = self.svc_family  # unprefixed — duploctl prefixes it
        result = execute_test(ecs_resource.create_service, body)
        assert result is not None
        print(f"ECS service create result: {result}")

    @pytest.mark.dependency(depends=["create_ecs_service"], scope="session")
    @pytest.mark.order(34)
    def test_find_ecs_service(self, ecs_resource):
        """Find the ECS service by task definition family name."""
        result = execute_test(ecs_resource.find_service_family, ecs_resource.prefixed_name(self.svc_family))
        assert result is not None
        svc = result.get("DuploEcsService", {})
        assert svc.get("Name") or svc.get("TaskDefinition"), \
            f"Unexpected service family response: {result}"
        print(f"ECS service found: {result.get('EcsServiceName')}")

    # ── update_image ──────────────────────────────────────────────────────────

    @pytest.mark.dependency(name="update_ecs_image", depends=["create_ecs_service"], scope="session")
    @pytest.mark.order(35)
    def test_update_image(self, ecs_resource):
        """Update the service task definition to a new image and wait for deployment.

        Wait is enabled. The wait loop must tolerate the window immediately after
        CreateEcsService where AWS has not yet registered any deployment — that
        state should raise DuploStillWaiting (keep polling), NOT DuploFailedResource
        (hard stop). A hard-fail here means the wait logic is wrong.
        """
        ecs_resource.duplo.wait = True
        try:
            result = execute_test(ecs_resource.update_image, self.svc_family, image=_UPDATED_IMAGE)
            assert result is not None
            # Confirm the running task definition actually reflects the new image.
            svc_def = ecs_resource.find_def(self.svc_family)
            assert svc_def["ContainerDefinitions"][0]["Image"] == _UPDATED_IMAGE, (
                f"Task def image not updated: {svc_def['ContainerDefinitions'][0]['Image']}"
            )
            print(f"update_image result: {result}")
        finally:
            ecs_resource.duplo.wait = False

    # ── run_task / list_tasks ─────────────────────────────────────────────────

    @pytest.mark.dependency(name="run_ecs_task", depends=["register_task_taskdef"], scope="session")
    @pytest.mark.order(36)
    def test_run_task(self, ecs_resource):
        """Run the standalone task definition once and wait for it to complete.

        The task runs 'echo ... && sleep 30' then exits. The wait passes when
        DesiredStatus == LastStatus (both STOPPED), confirming a clean completion.
        """
        ecs_resource.duplo.wait = True
        try:
            result = execute_test(ecs_resource.run_task, self.task_family, replicas=1)
            assert result is not None
            print(f"run_task result: {result}")
        finally:
            ecs_resource.duplo.wait = False

    @pytest.mark.dependency(depends=["run_ecs_task"], scope="session")
    @pytest.mark.order(37)
    def test_list_tasks(self, ecs_resource):
        """List tasks for the task definition family."""
        prefixed = ecs_resource.prefixed_name(self.task_family)
        result = execute_test(ecs_resource.list_tasks, prefixed)
        assert isinstance(result, list)
        print(f"Tasks found: {len(result)}")

    # ── cleanup ───────────────────────────────────────────────────────────────

    @pytest.mark.dependency(depends=["create_ecs_service"], scope="session")
    @pytest.mark.order(995)
    def test_delete_ecs_service(self, ecs_resource):
        """Delete the ECS service."""
        prefixed = ecs_resource.prefixed_name(self.svc_family)
        result = execute_test(ecs_resource.delete_service, prefixed)
        assert result is not None
        print(f"delete_service result: {result}")
