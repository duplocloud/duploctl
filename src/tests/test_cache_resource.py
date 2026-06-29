import os
import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.unit
class TestCacheResource:
  def test_clear_command(self, tmp_path):
    """Test the cache resource clear command calls clear_all_caches."""
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir)

    # Create some fake cache files.
    for name in ["host1-duplo-creds.json", "host2.cooldown", "other.json"]:
      with open(os.path.join(cache_dir, name), "w") as f:
        f.write("{}")

    mock_duplo = MagicMock()
    mock_duplo.cache_dir = cache_dir

    from duplo_resource.cache import DuploCache
    resource = DuploCache(mock_duplo)
    result = resource.clear()

    assert result == {"message": "Cleared 3 cached file(s)"}
    assert os.listdir(cache_dir) == []

  def test_clear_command_empty(self, tmp_path):
    """Test the cache resource clear command with zero files."""
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir)

    mock_duplo = MagicMock()
    mock_duplo.cache_dir = cache_dir

    from duplo_resource.cache import DuploCache
    resource = DuploCache(mock_duplo)
    result = resource.clear()

    assert result == {"message": "Cleared 0 cached file(s)"}

  def test_clear_command_nonexistent_dir(self, tmp_path):
    """Test clear command with nonexistent dir returns 0."""
    cache_dir = str(tmp_path / "nonexistent")

    mock_duplo = MagicMock()
    mock_duplo.cache_dir = cache_dir

    from duplo_resource.cache import DuploCache
    resource = DuploCache(mock_duplo)
    result = resource.clear()

    assert result == {"message": "Cleared 0 cached file(s)"}

  def test_clear_skips_subdirectories(self, tmp_path):
    """Test clear command only removes files, not subdirectories."""
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir)

    with open(os.path.join(cache_dir, "file.json"), "w") as f:
      f.write("{}")
    os.makedirs(os.path.join(cache_dir, "subdir"))

    mock_duplo = MagicMock()
    mock_duplo.cache_dir = cache_dir

    from duplo_resource.cache import DuploCache
    resource = DuploCache(mock_duplo)
    result = resource.clear()

    assert result == {"message": "Cleared 1 cached file(s)"}
    assert "subdir" in os.listdir(cache_dir)
