import configparser
import os
import pytest
from duplocloud.client import DuploClient
from duplocloud.errors import DuploError

class TestJIT:
  
  @pytest.mark.integration
  @pytest.mark.order(10)
  def test_admin_aws_jit(self, duplo: DuploClient):
    duplo.isadmin = True
    r = duplo.load("jit")
    try:
      o = r.aws()
      assert o.get("SecretAccessKey", None) is not None
    except DuploError as e:
      pytest.fail(f"Failed to get admin credentials: {e}")
  
  @pytest.mark.integration
  @pytest.mark.order(10)
  def test_user_aws_jit(self, duplo: DuploClient):
    duplo.isadmin = False
    r = duplo.load("jit")
    try:
      o = r.aws()
      assert o.get("SecretAccessKey", None) is not None
    except DuploError as e:
      pytest.fail(f"Failed to get user credentials: {e}")
  
  @pytest.mark.integration
  @pytest.mark.order(10)
  def test_user_k8s_context(self, duplo: DuploClient):
    duplo.isadmin = False
    r = duplo.load("jit")
    try:
      o = r.k8s_context()
      assert o.get("Token", None) is not None
    except DuploError as e:
      pytest.fail(f"Failed to get user k8s credentials: {e}")
  
  @pytest.mark.integration
  @pytest.mark.order(10)
  def test_admin_k8s_context(self, duplo: DuploClient):
    duplo.isadmin = True
    r = duplo.load("jit")
    try:
      o = r.k8s_context()
      assert o.get("Token", None) is not None
    except DuploError as e:
      pytest.fail(f"Failed to get admin k8s credentials: {e}")
  
  @pytest.mark.integration
  @pytest.mark.order(10)
  def test_update_aws_config(self, duplo: DuploClient, tmp_path):
    config_file = tmp_path / "config"
    os.environ["AWS_CONFIG_FILE"] = str(config_file)
    r = duplo.load("jit")
    profile_name = "test_profile"
    result = r.update_aws_config(profile_name)
    assert "added" in result["message"].lower()
    config = configparser.ConfigParser()
    config.read(config_file)
    profile_section = f"profile {profile_name}"
    assert config.has_section(profile_section)
    assert config.get(profile_section, "region") == os.getenv("AWS_DEFAULT_REGION", "us-west-2")
    assert "duploctl jit aws" in config.get(profile_section, "credential_process")
    result = r.update_aws_config(profile_name)
    assert "updated" in result["message"].lower()
    os.environ.pop("AWS_CONFIG_FILE", None)
