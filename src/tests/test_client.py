import os
import time
import sys
import pytest

from duplocloud.errors import DuploError, DuploInvalidError
from duplocloud.client import DuploClient
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
    duplo.token
    print(e)

@pytest.mark.unit
def test_cache_dir():
  c = DuploClient(
    host=host,
    cache_dir=cache_dir)
  assert c.cache_dir == cache_dir
  random_data = {"foo": "bar"}
  cf = f"{cache_dir}/test.json"
  c.set_cached_item("test", random_data)
  assert os.path.exists(cf), f"Cache file {cf} not found"
  # now check if we can get the data back
  assert c.get_cached_item("test") == random_data, "Cached data does not match"
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
