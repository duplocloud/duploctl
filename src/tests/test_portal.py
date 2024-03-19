import pytest

from duplocloud.errors import DuploError
from duplocloud.client import DuploClient

duplo, _ = DuploClient.from_env()

class Testportal:

  @pytest.mark.integration
  def test_system_info(self):
    r = duplo.load("system")
    try:
      lot = r("info")
      assert lot["DefaultAwsPartition"] == "aws"
      # Check is EnabledFlags has atleast 1 value.
      assert len(lot["EnabledFlags"]) > 0
      # Check is AppConfigs has atleast 1 value.
      assert len(lot["AppConfigs"]) > 0
    except DuploError as e:
      pytest.fail(f"Failed to grab system info: {e}")
    # there is at least some information returned.
    assert len(lot) > 0

