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
    # Mock the find method to return service details
    mock_service_details = {
        "Name": "test-service",
        "Image": "nginx:latest",
        "Replicaset": "rs-123"
    }
    mocker.patch.object(service, 'find', return_value=mock_service_details)
    # Mock the wait method
    mocker.patch.object(service, 'wait')
    # Enable wait flag
    mock_client.wait = True
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
    # Mock the find method to return service details
    mock_service_details = {
        "Name": "test-service",
        "Status": "Running"
    }
    mocker.patch.object(service, 'find', return_value=mock_service_details)
    # Mock the wait method
    mocker.patch.object(service, '_wait')
    # Enable wait flag
    mock_client.wait = True
    service.restart("test-service")
    mock_client.post.assert_called_once_with(ANY)

@pytest.mark.unit
def test_stop_service(mocker):
    mock_client = mocker.MagicMock()
    service = DuploService(mock_client)
    # Mock the find method to return service details
    mock_service_details = {
        "Name": "test-service",
        "Status": "Running"
    }
    mocker.patch.object(service, 'find', return_value=mock_service_details)
    # Mock the wait method
    mocker.patch.object(service, 'wait')
    # Enable wait flag
    mock_client.wait = True
    service.stop("test-service")
    mock_client.post.assert_called_once_with(ANY)

@pytest.mark.unit
def test_start_service(mocker):
    mock_client = mocker.MagicMock()
    service = DuploService(mock_client)
    # Mock the find method to return service details
    mock_service_details = {
        "Name": "test-service",
        "Status": "Stopped"
    }
    mocker.patch.object(service, 'find', return_value=mock_service_details)
    # Mock the wait method
    mocker.patch.object(service, 'wait')
    # Enable wait flag
    mock_client.wait = True
    service.start("test-service")
    mock_client.post.assert_called_once_with(ANY)


@pytest.mark.unit
def test_list_pods(mocker):
    mock_client = mocker.MagicMock()
    service = DuploService(mock_client)

    target_service = "DuploServiceArgument"
    mocker.patch.object(service._pod_svc, "list", side_effect=[
        [{ "ControlledBy": { "QualifiedType": "kubernetes:apps/v1/ReplicaSet" }, "Name": target_service }], # positive happy path
        [{ "ControlledBy": { "QualifiedType": "wrong:qualifier/type" }, "Name": target_service }], # negative happy path
        [{ "Name": target_service }], # No ControlledBy but pod has name matching pods service argument
        [{ "Name": "NotMyIntendedService" }], # edge case: No ControlledBy and pod has name NOT matching pods service argument
        [{}], # edge case: no ControlledBy nor Name defined handled gracefully
        ])
    
    # belongs to a duplo service
    assert service.pods(target_service) == [{ "ControlledBy": { "QualifiedType": "kubernetes:apps/v1/ReplicaSet" }, "Name": target_service }]

    # does not belong to a duplo service, gets filtered out
    assert service.pods(target_service) == []

    # belongs to a duplo service (alternative case)
    assert service.pods(target_service) == [{ "Name": target_service }]

    # does not belong to a duplo service, gets filtered out
    assert service.pods(target_service) == []

    # does not belong to a duplo service, gets filtered out
    assert service.pods(target_service) == []
