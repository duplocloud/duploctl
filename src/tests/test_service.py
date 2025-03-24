import json
import pytest
from unittest.mock import ANY
from duplo_resource.service import DuploService
from duplocloud.errors import DuploError

@pytest.mark.unit
def test_create_service(mocker):
    mock_client = mocker.MagicMock()
    service = DuploService(mock_client)
    body = {"Name": "test-service", "Image": "nginx:latest"}
    
    service.create(body)
    mock_client.post.assert_called_once_with(ANY, body)

@pytest.mark.unit
def test_delete_service(mocker):
    mock_client = mocker.MagicMock()
    service = DuploService(mock_client)
    
    service.delete("test-service")
    mock_client.post.assert_called_once_with(ANY, {"Name": "test-service", "State": "delete"})

@pytest.mark.unit
def test_restart_service(mocker):
    mock_client = mocker.MagicMock()
    service = DuploService(mock_client)
    
    service.restart("test-service")
    mock_client.post.assert_called_once_with(ANY)

@pytest.mark.unit
def test_stop_service(mocker):
    mock_client = mocker.MagicMock()
    service = DuploService(mock_client)
    
    service.stop("test-service")
    mock_client.post.assert_called_once_with(ANY)

@pytest.mark.unit
def test_start_service(mocker):
    mock_client = mocker.MagicMock()
    service = DuploService(mock_client)
    
    service.start("test-service")
    mock_client.post.assert_called_once_with(ANY)
