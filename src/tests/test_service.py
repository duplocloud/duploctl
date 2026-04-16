import json
import pytest
from unittest.mock import ANY
from duplo_resource.service import DuploService
from duplocloud.errors import DuploError, DuploNotFound

@pytest.mark.unit
def test_create_service(mocker):
    mock_client = mocker.MagicMock()
    mock_client.load_client.return_value = mock_client
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
    mock_client.load_client.return_value = mock_client
    service = DuploService(mock_client)
    service.delete("test-service")
    mock_client.post.assert_called_once_with(ANY, {"Name": "test-service", "State": "delete"})

@pytest.mark.unit
def test_restart_service(mocker):
    mock_client = mocker.MagicMock()
    mock_client.load_client.return_value = mock_client
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
    mock_client.load_client.return_value = mock_client
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
    mock_client.load_client.return_value = mock_client
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
    mock_client.load_client.return_value = mock_client
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


@pytest.mark.unit
def test_find_raises_not_found_on_null_response(mocker):
  """V3 find endpoint returns 200 with null body for non-existent services."""
  mock_client = mocker.MagicMock()
  mock_client.load_client.return_value = mock_client
  service = DuploService(mock_client)
  mock_response = mocker.MagicMock()
  mock_response.json.return_value = None
  mock_client.get.return_value = mock_response
  # The fallback to super().find() should also fail for a missing service
  mocker.patch.object(
    DuploService.__bases__[0], 'find',
    side_effect=DuploNotFound("test-svc", "Service")
  )
  with pytest.raises(DuploNotFound):
    service.find("test-svc")


@pytest.mark.unit
def test_update_with_flat_yaml_body(mocker):
  """update() handles flat YAML body without Template wrapper."""
  mock_client = mocker.MagicMock()
  mock_client.load_client.return_value = mock_client
  mock_client.wait = False
  service = DuploService(mock_client)
  existing_service = {
    "Name": "test-svc",
    "Template": {
      "OtherDockerConfig": '{"Env":[]}',
      "AgentPlatform": 7,
      "AllocationTags": "tagA",
    }
  }
  mocker.patch.object(service, 'find', return_value=existing_service)
  flat_body = {"Name": "test-svc", "Image": "nginx:latest", "Replicas": 2}
  service.update("test-svc", body=flat_body)
  posted_body = mock_client.post.call_args[0][1]
  assert posted_body["OtherDockerConfig"] == '{"Env":[]}'
  assert posted_body["AgentPlatform"] == 7


@pytest.mark.unit
def test_update_with_template_wrapped_body(mocker):
  """update() handles standard Template-wrapped body from API response."""
  mock_client = mocker.MagicMock()
  mock_client.load_client.return_value = mock_client
  mock_client.wait = False
  service = DuploService(mock_client)
  wrapped_body = {
    "Name": "test-svc",
    "Template": {
      "OtherDockerConfig": '{"Env":[{"Name":"X","Value":"1"}]}',
      "AgentPlatform": 3,
    }
  }
  service.update("test-svc", body=wrapped_body)
  posted_body = mock_client.post.call_args[0][1]
  assert posted_body["OtherDockerConfig"] == \
    '{"Env":[{"Name":"X","Value":"1"}]}'
  assert posted_body["AgentPlatform"] == 3


@pytest.mark.unit
def test_update_env_empty_otherdockerconfig(mocker):
  """update_env() handles empty string OtherDockerConfig."""
  mock_client = mocker.MagicMock()
  mock_client.load_client.return_value = mock_client
  mock_client.wait = False
  service = DuploService(mock_client)
  service_with_empty_config = {
    "Name": "test-svc",
    "Template": {
      "OtherDockerConfig": "",
      "AllocationTags": "",
    }
  }
  mocker.patch.object(service, 'find', return_value=service_with_empty_config)
  service.update_env(
    "test-svc", setvar=[("MY_VAR", "val")],
    strategy="replace", deletevar=None
  )
  posted_body = mock_client.post.call_args[0][1]
  config = json.loads(posted_body["OtherDockerConfig"])
  assert config["Env"] == [{"Name": "MY_VAR", "Value": "val"}]
