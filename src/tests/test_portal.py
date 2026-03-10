import os
import pytest

from duplocloud.errors import DuploError
from duplocloud.controller import DuploCtl


@pytest.mark.integration
class Testportal:

  def test_system_info(self, duplo):
    r = duplo.load("system")
    try:
      info = r("info")
      assert info["DefaultAwsPartition"] == "aws"
      # Check is EnabledFlags has atleast 1 value.
      assert len(info["EnabledFlags"]) > 0
      # Check is AppConfigs has atleast 1 value.
      assert len(info["AppConfigs"]) > 0
    except DuploError as e:
      pytest.fail(f"Failed to grab system info: {e}")
    # there is at least some information returned.
    assert len(info) > 0

