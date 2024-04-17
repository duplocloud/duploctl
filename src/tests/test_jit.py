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
  
  

