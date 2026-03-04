import os
import time
import sys
import pytest

from duplocloud.errors import DuploError, DuploInvalidError
from duplocloud.controller import DuploClient
from tests.conftest import get_test_data

# current working directory as variable
cwd = os.getcwd()
host = "http://example.duplocloud.net/nothing/?foo=bar"
cache_dir = f"{cwd}/.tmp/cache"

@pytest.mark.unit
def test_new_config():
  c = DuploClient(host=host)
  assert c.host == "https://example.duplocloud.net"

@pytest.mark.unit
def test_at_least_host(mocker):
  """No Host Gets Error"""

  # Patch in a mock of the client's config file so this test doesn't depend on a specific local setup.
  # Alternatively, we could set the config_file arg of DuploClient to a YAML in the tests/files directory. A mock
  # exercises the constructor's default (and requires no changes to the test this was added to fix).
  duplo_config_file = '''
---
current-context: this
contexts:
- name: this
  tenant: none
  token: none

  # Host not set to intentionally trigger the expected error.
  # host: localhost
'''
  mocker.patch('builtins.open', mocker.mock_open(read_data=duplo_config_file))

  duplo = DuploClient()
  with pytest.raises(DuploError) as e:
    duplo.load_client("duplo").token
    print(e)

@pytest.mark.unit
def test_cache_dir():
  c = DuploClient(
    host=host,
    cache_dir=cache_dir)
  assert c.cache_dir == cache_dir
  random_data = {"foo": "bar"}
  cf = f"{cache_dir}/test.json"
  cache = c.load("cache")
  cache.set("test", random_data)
  assert os.path.exists(cf), f"Cache file {cf} not found"
  # now check if we can get the data back
  assert cache.get("test") == random_data, "Cached data does not match"
  # delete the cache file
  os.remove(cf)
  os.rmdir(cache_dir)

@pytest.mark.unit
def test_sanitize_host_with_http_scheme():
  """Test that hosts with http:// scheme are converted to https://"""
  c = DuploClient(host="http://example.duplocloud.net")
  assert c.host == "https://example.duplocloud.net"

@pytest.mark.unit
def test_sanitize_host_with_https_scheme():
  """Test that hosts with https:// scheme remain https://"""
  c = DuploClient(host="https://example.duplocloud.net")
  assert c.host == "https://example.duplocloud.net"

@pytest.mark.unit
def test_sanitize_host_without_scheme():
  """Test that hosts without scheme get https:// added"""
  c = DuploClient(host="example.duplocloud.net")
  assert c.host == "https://example.duplocloud.net"

@pytest.mark.unit
def test_sanitize_host_with_path_and_query():
  """Test that paths and query parameters are removed"""
  c = DuploClient(host="example.duplocloud.net/path?query=value")
  assert c.host == "https://example.duplocloud.net"

@pytest.mark.unit
def test_sanitize_host_with_trailing_slash():
  """Test that trailing slashes are handled correctly"""
  c = DuploClient(host="example.duplocloud.net/")
  assert c.host == "https://example.duplocloud.net"

@pytest.mark.unit
def test_load_model_returns_class():
  """load_model returns the Pydantic class for a known model name"""
  c = DuploClient(host="https://example.duplocloud.net")
  model_cls = c.load_model("AddTenantRequest")
  assert model_cls is not None, "Expected AddTenantRequest model class, got None"
  assert hasattr(model_cls, "model_validate"), "Expected a Pydantic model with model_validate"

@pytest.mark.unit
def test_load_model_unknown_returns_none():
  """load_model returns None for an unknown model name"""
  c = DuploClient(host="https://example.duplocloud.net")
  assert c.load_model("ThisModelDoesNotExist12345") is None

@pytest.mark.unit
def test_load_model_none_name_returns_none():
  """load_model returns None when called with None"""
  c = DuploClient(host="https://example.duplocloud.net")
  assert c.load_model(None) is None

@pytest.mark.unit
def test_load_model_is_lazy():
  """load_model triggers lazy loading — the model submodule should not be
  imported until load_model is actually called."""
  import duplocloud_sdk as sdk
  module_path = "duplocloud_sdk.models.add_tenant_request"
  # Clear the cached attribute and the submodule so we can observe the first load
  sdk.__dict__.pop("AddTenantRequest", None)
  sys.modules.pop(module_path, None)
  c = DuploClient(host="https://example.duplocloud.net")
  # The top-level duplocloud_sdk is imported (it's a required dep), but the
  # individual model submodule should not yet be loaded.
  assert module_path not in sys.modules, "Model submodule was pre-loaded before load_model was called"
  c.load_model("AddTenantRequest")
  assert module_path in sys.modules, "Model submodule should be loaded after load_model is called"

@pytest.mark.unit
def test_load_model_completes_quickly():
  """load_model should complete well under 3 seconds even on a cold import"""
  module_path = "duplocloud_sdk.models.add_tenant_request"
  sys.modules.pop(module_path, None)
  c = DuploClient(host="https://example.duplocloud.net")
  start = time.monotonic()
  c.load_model("AddTenantRequest")
  elapsed = time.monotonic() - start
  assert elapsed < 3.0, f"load_model took {elapsed:.2f}s — lazy loading may not be working"

@pytest.mark.unit
def test_validate_model_returns_serialized_dict():
  """validate_model returns a serialized dict using field aliases"""
  c = DuploClient(host="https://example.duplocloud.net")
  model_cls = c.load_model("AddTenantRequest")
  data = get_test_data("tenant")
  result = c.validate_model(model_cls, data)
  assert isinstance(result, dict)
  assert result["AccountName"] == data["AccountName"]
  assert result["PlanID"] == data["PlanID"]

@pytest.mark.unit
def test_validate_model_raises_on_invalid_data():
  """validate_model raises DuploInvalidError when data fails validation"""
  c = DuploClient(host="https://example.duplocloud.net")
  model_cls = c.load_model("AddTenantRequest")
  # AccountName expects a string — pass an invalid type to trigger failure
  bad_data = {"AccountName": {"nested": "object"}, "PlanID": "default"}
  with pytest.raises(DuploInvalidError):
    c.validate_model(model_cls, bad_data)

@pytest.mark.unit
def test_validate_flag_defaults_to_false():
  """validate defaults to False on DuploClient"""
  c = DuploClient(host="https://example.duplocloud.net")
  assert c.validate is False

@pytest.mark.unit
def test_validate_flag_can_be_set():
  """validate=True can be set on DuploClient"""
  c = DuploClient(host="https://example.duplocloud.net", validate=True)
  assert c.validate is True

# ---------------------------------------------------------------------------
# __call__ dispatch tests — verifies kwargs threading, query override,
# and format passthrough.
# ---------------------------------------------------------------------------

@pytest.fixture
def duplo_with_mock_resource(mocker):
  """A DuploClient whose load() returns a mock resource that echoes back
  a known list of dicts, so we can test the full __call__ → filter → format
  chain without any HTTP calls."""
  c = DuploClient(host="https://example.duplocloud.net")
  mock_resource = mocker.MagicMock()
  mock_resource.__doc__ = "mock resource"
  mock_resource.return_value = [
    {"Name": "alpha", "Status": "running"},
    {"Name": "beta", "Status": "stopped"},
  ]
  mocker.patch.object(c, "load", return_value=mock_resource)
  return c

@pytest.mark.unit
def test_call_without_query(duplo_with_mock_resource):
  """duplo(resource, command) returns formatted json string of full data"""
  result = duplo_with_mock_resource("tenant", "list")
  assert isinstance(result, str)
  assert "alpha" in result
  assert "beta" in result

@pytest.mark.unit
def test_call_with_query_override(duplo_with_mock_resource):
  """duplo(resource, command, query=...) filters with the per-call query"""
  result = duplo_with_mock_resource("tenant", "list", query="[?Name=='alpha'].Name")
  assert isinstance(result, str)
  assert "alpha" in result
  assert "beta" not in result

@pytest.mark.unit
def test_call_query_override_does_not_affect_global(duplo_with_mock_resource):
  """Per-call query does not mutate the global self.query"""
  c = duplo_with_mock_resource
  assert c.query is None
  c("tenant", "list", query="[0].Name")
  assert c.query is None

@pytest.mark.unit
def test_call_global_query_still_works(duplo_with_mock_resource):
  """When self.query is set and no per-call query, the global is used"""
  c = duplo_with_mock_resource
  c.query = "[?Name=='beta']"
  result = c("tenant", "list")
  assert "beta" in result
  assert "alpha" not in result
  c.query = None

@pytest.mark.unit
def test_call_query_override_beats_global(duplo_with_mock_resource):
  """Per-call query takes precedence over the global self.query"""
  c = duplo_with_mock_resource
  c.query = "[?Name=='beta']"
  result = c("tenant", "list", query="[?Name=='alpha']")
  assert "alpha" in result
  assert "beta" not in result
  c.query = None

@pytest.mark.unit
def test_call_passes_kwargs_to_resource(duplo_with_mock_resource, mocker):
  """kwargs like body= flow through to the resource __call__"""
  c = duplo_with_mock_resource
  mock_resource = c.load("tenant")
  body = {"Name": "new-tenant"}
  c("tenant", "create", body=body)
  mock_resource.assert_called_with("create", body=body)

@pytest.mark.unit
def test_call_format_none_returns_raw_data(mocker):
  """When output is None, format() returns the raw data object"""
  c = DuploClient(host="https://example.duplocloud.net")
  c.output = None
  mock_resource = mocker.MagicMock()
  mock_resource.__doc__ = "mock resource"
  mock_resource.return_value = [{"Name": "alpha"}]
  mocker.patch.object(c, "load", return_value=mock_resource)
  result = c("tenant", "list")
  assert isinstance(result, list)
  assert result == [{"Name": "alpha"}]

@pytest.mark.unit
def test_call_none_result_returns_none(duplo_with_mock_resource):
  """When the command returns None, __call__ returns None"""
  c = duplo_with_mock_resource
  c.load("tenant").return_value = None
  result = c("tenant", "list")
  assert result is None
