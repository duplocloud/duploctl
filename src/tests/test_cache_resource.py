import os
import pytest
from unittest.mock import MagicMock


@pytest.mark.unit
class TestDuploCacheClear:
  def test_clear_removes_files(self, tmp_path):
    """Test that DuploClient.clear_cache removes files from cache dir."""
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir)

    # Create some fake cache files.
    for name in ["host1-duplo-creds.json", "host2.cooldown", "other.json"]:
      with open(os.path.join(cache_dir, name), "w") as f:
        f.write("{}")

    mock_client = MagicMock()
    mock_client.cache_dir = cache_dir

    from duplocloud.client import DuploClient
    count = DuploClient.clear_cache(mock_client)
    assert count == 3
    assert os.listdir(cache_dir) == []

  def test_clear_empty_dir(self, tmp_path):
    """Test clear_cache on an empty directory returns 0."""
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir)

    mock_client = MagicMock()
    mock_client.cache_dir = cache_dir

    from duplocloud.client import DuploClient
    count = DuploClient.clear_cache(mock_client)
    assert count == 0

  def test_clear_nonexistent_dir(self, tmp_path):
    """Test clear_cache with nonexistent dir returns 0."""
    cache_dir = str(tmp_path / "nonexistent")

    mock_client = MagicMock()
    mock_client.cache_dir = cache_dir

    from duplocloud.client import DuploClient
    count = DuploClient.clear_cache(mock_client)
    assert count == 0

  def test_clear_skips_subdirectories(self, tmp_path):
    """Test clear_cache only removes files, not subdirectories."""
    cache_dir = str(tmp_path / "cache")
    os.makedirs(cache_dir)

    with open(os.path.join(cache_dir, "file.json"), "w") as f:
      f.write("{}")
    os.makedirs(os.path.join(cache_dir, "subdir"))

    mock_client = MagicMock()
    mock_client.cache_dir = cache_dir

    from duplocloud.client import DuploClient
    count = DuploClient.clear_cache(mock_client)
    assert count == 1
    assert "subdir" in os.listdir(cache_dir)


@pytest.mark.unit
class TestCacheResource:
  def test_clear_command(self, tmp_path):
    """Test the cache resource clear command delegates to DuploClient.clear_cache."""
    mock_client = MagicMock()
    mock_client.clear_cache.return_value = 5

    from duplo_resource.cache import DuploCache
    resource = DuploCache(mock_client)
    result = resource.clear()

    mock_client.clear_cache.assert_called_once()
    assert result == {"message": "Cleared 5 cached file(s)"}

  def test_clear_command_empty(self):
    """Test the cache resource clear command with zero files."""
    mock_client = MagicMock()
    mock_client.clear_cache.return_value = 0

    from duplo_resource.cache import DuploCache
    resource = DuploCache(mock_client)
    result = resource.clear()

    assert result == {"message": "Cleared 0 cached file(s)"}
