import os
import pytest
import random
import yaml
import pathlib
from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError


def _duplo_from_env() -> DuploCtl:
  """Construct a DuploCtl directly from environment variables.

  Deliberately avoids DuploCtl.from_env() which calls parse_known_args()
  against sys.argv — that causes conflicts with pytest's own flags (e.g.
  pytest -q vs duploctl --query/-q).
  """
  return DuploCtl(
    host=os.getenv("DUPLO_HOST"),
    token=os.getenv("DUPLO_TOKEN"),
    tenant=os.getenv("DUPLO_TENANT"),
  )


def pytest_addoption(parser):
  infra = os.getenv("DUPLO_INFRA", None)
  parser.addoption(
    "--infra", action="store", default=infra,
    help="Infrastructure name to target. Create is skipped if it already exists.")
  parser.addoption(
    "--tenant", action="store", default=None,
    help="Use an existing tenant by name. Falls back to DUPLO_TENANT env var, then infra name.")
  parser.addoption(
    "--region", action="store", default=None,
    help="AWS region override for infrastructure creation. Defaults to the region in the data file.")
  parser.addoption(
    "--owned", action="store_true", default=False,
    help="Treat the infra and tenant as owned by this session regardless of whether they pre-existed. "
         "Forces owns_infra and owns_tenant to True, enabling teardown. "
         "Used by CI teardown jobs that run after parallel resource jobs finish.")
  parser.addoption(
    "--names-file", action="store", default=None,
    help="Path to write the resolved infra and tenant names (KEY=value format). "
         "Used by CI to pass names from lifecycle job to resource/teardown jobs.")
  parser.addoption(
    "--no-teardown", action="store_true", default=False,
    help="Skip infra/tenant deletion tests. "
         "Used by lifecycle and resource jobs so only the dedicated teardown job deletes.")


_INFRA_DATA = {
    "k8s":   "infrastructure-k8s",
    "ecs":   "infrastructure-ecs",
    "duplo": "infrastructure",
}


def _is_unit_run(config) -> bool:
  """Return True if this pytest session is running only unit tests."""
  markexpr = config.getoption("markexpr", default="", skip=True) or ""
  return "unit" in markexpr


def pytest_configure(config):
  """Validate marker combinations and tenant/infra consistency before collection.

  Resolves tenant with the same precedence as the tenant_name fixture:
    --tenant  >  DUPLO_TENANT env var  >  infra_name (same name as infra)

  If the resolved tenant already exists on a different infra, exit immediately
  with a clear message telling the user to pass --tenant explicitly.
  """
  markexpr = config.getoption("markexpr", default="", skip=True) or ""
  if "unit" in markexpr and "integration" in markexpr:
    pytest.exit(
      "ERROR: 'unit' and 'integration' are mutually exclusive markers. "
      "Run them in separate pytest invocations.",
      returncode=1,
    )
  # Skip all integration-specific validation for unit test runs.
  if _is_unit_run(config):
    return
  if "k8s" in markexpr and "ecs" in markexpr:
    pytest.exit(
      "ERROR: Cannot select both 'k8s' and 'ecs' — "
      "they are mutually exclusive infra types. Choose one.",
      returncode=1,
    )
  infra = config.getoption("--infra", default=None, skip=True) or None
  # Resolve tenant: explicit arg > DUPLO_TENANT > infra (same name)
  tenant = (
    config.getoption("--tenant", default=None, skip=True)
    or os.getenv("DUPLO_TENANT")
    or infra
  ) or None
  # Only check when both are known and differ — identical names are always safe.
  if not infra or not tenant or infra == tenant:
    return
  try:
    d = _duplo_from_env()
    existing = d.load("tenant").find(tenant)
    plan_id = existing.get("PlanID", "")
    if plan_id and plan_id != infra:
      pytest.exit(
        f"\nERROR: Tenant '{tenant}' already exists but belongs to infra "
        f"'{plan_id}', not '{infra}'.\n"
        f"Either pass --infra {plan_id} to match the tenant's infra, "
        f"or choose a --tenant name that does not exist yet.\n",
        returncode=1,
      )
  except DuploError:
    # Tenant does not exist yet — fine, the create lifecycle handles it.
    pass

@pytest.fixture(scope='session', autouse=True)
def infra_name(pytestconfig) -> str:
  """The infrastructure name for this test session.

  Returns None for unit test runs — no infra resolution needed.

  Resolution order:
    1. --infra <name>  (explicit CLI arg or DUPLO_INFRA env var)
    2. If --tenant / DUPLO_TENANT is given but no --infra:
         a. Tenant already exists  → use its PlanID as the infra name.
         b. Tenant does not exist  → use the tenant name as the infra name.
    3. Neither given  → generate a unique name (duploctl{1000-9999}).
  """
  if _is_unit_run(pytestconfig):
    return None

  explicit_infra = pytestconfig.getoption("infra") or None
  if explicit_infra:
    return explicit_infra

  # No --infra given. A tenant hint can tell us which infra to use.
  tenant_hint = pytestconfig.getoption("tenant") or os.getenv("DUPLO_TENANT") or None
  if tenant_hint:
    try:
      d = _duplo_from_env()
      existing = d.load("tenant").find(tenant_hint)
      plan_id = existing.get("PlanID", "")
      if plan_id:
        return plan_id  # tenant exists — use its infra
    except DuploError:
      pass  # tenant doesn't exist yet — fall through
    # Tenant doesn't exist: infra name mirrors the tenant name.
    return tenant_hint

  inc = random.randint(1000, 9999)
  return f"duploctl{inc}"

@pytest.fixture(scope='session', autouse=True)
def tenant_name(pytestconfig, infra_name) -> str:
  """The tenant name for this test session.

  Precedence:
    1. --tenant <name>    (explicit CLI arg)
    2. DUPLO_TENANT       (environment variable)
    3. infra_name         (from --infra / DUPLO_INFRA, or randomly generated)

  If DUPLO_TENANT is set in the shell and --infra targets a different infra,
  pytest_configure will catch the mismatch and tell you to pass --tenant
  explicitly to override it.
  """
  explicit_tenant = pytestconfig.getoption("tenant") or None
  if explicit_tenant:
    return explicit_tenant
  env_tenant = os.getenv("DUPLO_TENANT")
  if env_tenant:
    return env_tenant
  return infra_name

@pytest.fixture(scope='session')
def infra_type(pytestconfig) -> str:
  """Infra type: 'k8s', 'ecs', or 'duplo' (default). Inferred from -m expression."""
  markexpr = pytestconfig.getoption("markexpr", default="") or ""
  if "k8s" in markexpr:
    return "k8s"
  if "ecs" in markexpr:
    return "ecs"
  return "duplo"

@pytest.fixture(scope='session')
def region(pytestconfig) -> str | None:
  """AWS region override for infrastructure creation. None means use the data file's value."""
  return pytestconfig.getoption("region") or None

@pytest.fixture(scope='session')
def owns_infra(pytestconfig, infra_name) -> bool:
  """True if this session is responsible for creating (and thus destroying) the infra.

  Returns False — do not delete — when:
    - --infra was given explicitly AND that infra already existed, OR
    - the infra name was resolved from an existing tenant's PlanID (tenant-hint path).

  In both cases the infrastructure belongs to someone else and must not be torn down.

  --owned overrides all checks and forces True — used by CI teardown jobs.
  --no-teardown forces False — used by lifecycle and resource jobs.
  """
  if pytestconfig.getoption("no_teardown", default=False):
    return False
  if pytestconfig.getoption("owned", default=False):
    return True
  explicit_infra = pytestconfig.getoption("infra", default=None) or None
  if explicit_infra:
    try:
      _duplo_from_env().load("infrastructure").find(explicit_infra)
      return False  # pre-existing — not ours
    except DuploError:
      return True   # doesn't exist yet — we'll create it

  # No --infra flag: was the name resolved from an already-existing tenant?
  tenant_hint = pytestconfig.getoption("tenant", default=None) or os.getenv("DUPLO_TENANT") or None
  if tenant_hint:
    try:
      existing = _duplo_from_env().load("tenant").find(tenant_hint)
      if existing.get("PlanID"):
        return False  # infra resolved from a pre-existing tenant — not ours
    except DuploError:
      pass

  return True  # random or derived name — we own it


@pytest.fixture(scope='session')
def owns_tenant(pytestconfig, tenant_name, owns_infra) -> bool:
  """True if this session is responsible for creating (and thus destroying) the tenant.

  Returns False — do not delete — when:
    - The infra is pre-existing (we don't own its tenants either), OR
    - --tenant / DUPLO_TENANT was given explicitly AND that tenant already existed.

  Only returns True when the tenant name was derived/random and the tenant
  did not exist before this session started.

  --owned overrides all checks and forces True — used by CI teardown jobs.
  --no-teardown forces False — used by lifecycle and resource jobs.
  """
  if pytestconfig.getoption("no_teardown", default=False):
    return False
  if pytestconfig.getoption("owned", default=False):
    return True
  if not owns_infra:
    return False  # never destroy a tenant in an infra we didn't create

  explicit_tenant = pytestconfig.getoption("tenant", default=None) or os.getenv("DUPLO_TENANT") or None
  if explicit_tenant:
    try:
      _duplo_from_env().load("tenant").find(tenant_name)
      return False  # pre-existing — not ours
    except DuploError:
      return True   # doesn't exist yet — we'll create it

  return True  # name derived from infra we own — we own the tenant too


@pytest.fixture(scope='session', autouse=True)
def duplo(pytestconfig, tenant_name: str):
  """The shared DuploCtl client for the test session.

  Returns None for unit test runs — no live client needed.

  duplo.tenant is always set from the tenant_name fixture so all
  tenant-scoped resources resolve to the correct tenant without any
  test needing to set it manually.
  """
  if _is_unit_run(pytestconfig):
    return None
  d = _duplo_from_env()
  d.load_client("duplo").disable_get_cache()
  d.tenant = tenant_name
  return d

@pytest.fixture(scope="session", autouse=True)
def session_info(pytestconfig, duplo, infra_name, tenant_name, infra_type, owns_infra, owns_tenant):
  """Print session targeting info at the start of every integration test run."""
  if duplo is None:
    yield
    return
  no_teardown = pytestconfig.getoption("no_teardown", default=False)
  owned_flag = " --no-teardown" if no_teardown else (
    " --owned" if pytestconfig.getoption("owned", default=False) else ""
  )
  print(
    f"\n"
    f"  host:        {duplo.host}\n"
    f"  infra:       {infra_name}  (owns={owns_infra})\n"
    f"  tenant:      {tenant_name}  (owns={owns_tenant})\n"
    f"  infra_type:  {infra_type}{owned_flag}\n"
  )
  names_file = pytestconfig.getoption("names_file", default=None)
  if names_file:
    with open(names_file, "w") as f:
      f.write(f"infra={infra_name}\n")
      f.write(f"tenant={tenant_name}\n")
  yield


@pytest.fixture(scope="session", autouse=True)
def cleanup(duplo):
  """Session-scoped cleanup marker.

  Actual infra/tenant teardown is handled by the lifecycle test methods
  (test_find_delete_tenant, test_find_delete_infra) which are gated by
  pytest-dependency — they only run if their corresponding create tests passed.
  """
  yield

@pytest.fixture
def test_data(request) -> tuple[str, dict]:
  """Fixture to load test data from a yaml file.
  
  Splits like this: kind::file
  example with a data file named big_host with host data would be: host::big_host
  """
  test_id = request.param.split("::")
  kind = test_id[0]
  file = test_id[-1]
  print(f"Loading test data for {kind} from {file}")
  data = get_test_data(file)
  return (kind, data)

def get_test_data(name) -> dict:
  # get the directory this file is in
  dir = pathlib.Path(__file__).parent.resolve()
  f = f"{dir}/data/{name}.yaml"
  with open(f, 'r') as stream:
    return yaml.safe_load(stream)
