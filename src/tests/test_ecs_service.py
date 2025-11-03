import pytest
from unittest.mock import ANY, MagicMock
from duplo_resource.ecs_service import DuploEcsService
from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from tests.test_utils import execute_test, assert_response

@pytest.mark.unit
def test_update_image_with_container(mocker):
    mock_client = mocker.MagicMock()
    service = DuploEcsService(mock_client)
    # Mock task definition with multiple containers
    mock_task_def = {
        "ContainerDefinitions": [
            {"Name": "app", "Image": "old-image:1"},
            {"Name": "sidecar", "Image": "sidecar:1"}
        ]
    }
    # Mock service family
    mock_service_family = {
        "DuploEcsService": {
            "TaskDefinition": "old-arn"
        }
    }
    # Mock the required methods
    mocker.patch.object(service, 'prefixed_name', return_value="test-service")
    mocker.patch.object(service, 'find_def', return_value=mock_task_def)
    mocker.patch.object(service, 'update_taskdef', return_value={"arn": "new-arn"})
    mocker.patch.object(service, 'find_service_family', return_value=mock_service_family)
    mocker.patch.object(service, 'update_service')
    mocker.patch.object(service, 'wait')
    # Enable wait flag
    mock_client.wait = True
    # Test updating specific container
    result = execute_test(service.update_image, "test-service", container_image=[("sidecar", "new-image:2")])
    # Verify the container image was updated
    assert mock_task_def["ContainerDefinitions"][1]["Image"] == "new-image:2"
    assert mock_task_def["ContainerDefinitions"][0]["Image"] == "old-image:1"
    # Verify service was updated with new task definition
    service.update_service.assert_called_once_with(mock_service_family["DuploEcsService"])
    assert_response(result, "Updating a task definition and its corresponding service.")

@pytest.mark.unit
def test_update_image_without_container(mocker):
    mock_client = mocker.MagicMock()
    service = DuploEcsService(mock_client)
    # Mock task definition with single container
    mock_task_def = {
        "ContainerDefinitions": [
            { "Name": "app", "Image": "old-image:1" }
        ]
    }
    # Mock service family
    mock_service_family = {
        "DuploEcsService": {
            "TaskDefinition": "old-arn"
        }
    }
    # Mock the required methods
    mocker.patch.object(service, 'prefixed_name', return_value="test-service")
    mocker.patch.object(service, 'find_def', return_value=mock_task_def)
    mocker.patch.object(service, 'update_taskdef', return_value={"arn": "new-arn"})
    mocker.patch.object(service, 'find_service_family', return_value=mock_service_family)
    mocker.patch.object(service, 'update_service')
    mocker.patch.object(service, 'wait')
    # Enable wait flag
    mock_client.wait = True
    # Test updating without specifying container (should update first container)
    result = execute_test(service.update_image, "test-service", image="new-image:2")
    # Verify the first container image was updated
    assert mock_task_def["ContainerDefinitions"][0]["Image"] == "new-image:2"
    # Verify service was updated with new task definition
    service.update_service.assert_called_once_with(mock_service_family["DuploEcsService"])
    assert_response(result, "Updating a task definition and its corresponding service.")

@pytest.mark.unit
def test_update_image_no_service(mocker):
    mock_client = mocker.MagicMock()
    service = DuploEcsService(mock_client)
    # Mock task definition
    mock_task_def = {
        "ContainerDefinitions": [
            {"Name": "app", "Image": "old-image:1"}
        ]
    }
    # Mock the required methods
    mocker.patch.object(service, 'prefixed_name', return_value="test-service")
    mocker.patch.object(service, 'find_def', return_value=mock_task_def)
    mocker.patch.object(service, 'update_taskdef', return_value={"arn": "new-arn"})
    mocker.patch.object(service, 'find_service_family', side_effect=DuploError("Service not found"))
    # Test updating image when no service exists
    result = execute_test(service.update_image, "test-service", image="new-image:2")
    # Verify the image was updated in task definition
    assert mock_task_def["ContainerDefinitions"][0]["Image"] == "new-image:2"
    # Verify appropriate message is returned
    assert_response(result, "No Service Configured, only the definition is updated.")

@pytest.mark.unit
def test_find_def_uses_taskdef_family_from_service(mocker):
    mock_client = mocker.MagicMock()
    service = DuploEcsService(mock_client)

    # Arrange
    mocker.patch.object(service, 'prefixed_name', return_value='prefixed-svc')
    mocker.patch.object(service, 'find_service_family', return_value={
        'TaskDefFamily': 'actual-family'
    })
    mock_find_tdf = mocker.patch.object(service, 'find_task_def_family', return_value={
        'VersionArns': ['arn:tdf:1', 'arn:tdf:2']
    })
    mock_find_by_arn = mocker.patch.object(service, 'find_def_by_arn', return_value={
        'TaskDefinitionArn': 'arn:tdf:2'
    })

    # Act
    result = execute_test(service.find_def, 'svc-name')

    # Assert
    mock_find_tdf.assert_called_once_with('actual-family')
    mock_find_by_arn.assert_called_once_with('arn:tdf:2')
    assert result == {'TaskDefinitionArn': 'arn:tdf:2'}

@pytest.mark.unit
def test_manual_taskdef_mapping(mocker):
    mock_client = mocker.MagicMock()
    service = DuploEcsService(mock_client)

    existing_taskdef = {
        "Family": "my-family",
        "ContainerDefinitions": [
            {
                "Name": "app",
                "Image": "my-image:1",
                "CredentialSpecs" : [],
                "Environment" : [
                    {
                        "Name" : "ENV_VAR1",
                        "Value" : "VALUE1"
                    },
                    {
                        "Name" : "ENV_VAR2",
                        "Value" : "VALUE2"
                    },
                ],
                "EnvironmentFiles" : [
                    {
                    "Type" : {
                        "Value" : "s3"
                    },
                    "Value" : "arn:aws:s3:::my-example-bucket/sample.env"
                    }
                ],
                "LogConfiguration" : {
                    "LogDriver" : {
                        "Value" : "dummy-driver"
                    },
                    "Options" : {
                        "OptionKey1": "OptionValue1",
                        "OptionKey2": "OptionValue2"
                    },
                    "SecretOptions" : []
                },
                "stopTimeout" : 120,
                "MountPoints" : [
                    {
                        "ContainerPath" : "/mnt/my-volume",
                        "ReadOnly" : "false",
                        "SourceVolume" : "my-volume"
                    }
                ]
            }
        ],
        "Volumes": [
            {
                "ConfiguredAtLaunch": False,
                "EfsVolumeConfiguration": {
                    "FileSystemId": "<my-efs-id>",
                    "RootDirectory": "/",
                    "TransitEncryption": {
                        "Value": "ENABLED"
                    }
                },
                "Name": "my-volume"
            }
        ]
    }

    # Even though this is a private method and should not be part of a behavior driven test suite
    # Issues with this method has caused enough problems to justify this extra coverage
    result = execute_test(service._DuploEcsService__ecs_task_def_body, existing_taskdef)

    assert result["Volumes"] == existing_taskdef["Volumes"]
    assert result["Family"] == existing_taskdef["Family"]
    assert result["ContainerDefinitions"] == existing_taskdef["ContainerDefinitions"]
