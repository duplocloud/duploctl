import pytest
from unittest.mock import ANY, MagicMock
from duplo_resource.ecs_service import DuploEcsService
from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploStillWaiting
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
    assert_response(result, "ECS Service and Task Definition updated successfully.")

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
    mocker.patch.object(service, '_wait_on_service')
    # Enable wait flag
    mock_client.wait = True
    # Test updating without specifying container (should update first container)
    result = execute_test(service.update_image, "test-service", image="new-image:2")
    # Verify the first container image was updated
    assert mock_task_def["ContainerDefinitions"][0]["Image"] == "new-image:2"
    # Verify service was updated with new task definition
    service.update_service.assert_called_once_with(mock_service_family["DuploEcsService"])
    assert_response(result, "ECS Service and Task Definition updated successfully.")

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
def test_taskdef_mapping_comprehensive_enough(mocker):
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

@pytest.mark.unit
def test_taskdef_mapping_properly_sanitizes_properties(mocker):
    mock_client = mocker.MagicMock()
    service = DuploEcsService(mock_client)
    existing_taskdef = {
        "Family": "my-family",
        "ContainerDefinitions": [
            {
                "Name": "app",
                "Image": "my-image:1",
                "Cpu": 0,
                "Memory": 0,
                "MemoryReservation": 0,
                "StartTimeout": 0,
                "StopTimeout": 0,
                "LinuxParameters": {
                    "SharedMemorySize": 0
                },
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
                    },
                    "TransitEncryptionPort": 0
                },
                "Name": "my-volume"
            }
        ]
    }

    result = execute_test(service._DuploEcsService__ecs_task_def_body, existing_taskdef)

    assert "Cpu" not in result["ContainerDefinitions"][0]
    assert "Memory" not in result["ContainerDefinitions"][0]
    assert "MemoryReservation" not in result["ContainerDefinitions"][0]
    assert "StartTimeout" not in result["ContainerDefinitions"][0]
    assert "StopTimeout" not in result["ContainerDefinitions"][0]
    assert "SharedMemorySize" not in result["ContainerDefinitions"][0]["LinuxParameters"]

    assert "TransitEncryptionPort" not in result["Volumes"][0]["EfsVolumeConfiguration"]

@pytest.mark.unit
def test_wait_on_task(mocker):
    mock_client = mocker.MagicMock()
    service = DuploEcsService(mock_client)

    mock_tasks_pending = [
        { "TaskDefinitionArn": "old_arn", "DesiredStatus": "Stopped", "LastStatus": "Draining" },
        { "TaskDefinitionArn": "my_target_taskdef_arn", "DesiredStatus": "Running", "LastStatus": "Provisioning" },
    ]

    mock_tasks_stable = [
        { "TaskDefinitionArn": "old_arn", "DesiredStatus": "Stopped", "LastStatus": "Stopped" },
        { "TaskDefinitionArn": "my_target_taskdef_arn", "DesiredStatus": "Running", "LastStatus": "Running" },
    ]

    mocker.patch.object(service, "list_tasks", side_effect=[mock_tasks_pending, mock_tasks_stable])

    # catches wait for cases when service is still in previous state and new deployment has not started
    with pytest.raises(DuploStillWaiting):
        service._wait_on_task("test")

    # settled ecs tasks state should just run and not throw
    service._wait_on_task("test")

@pytest.mark.unit
def test_wait_on_service(mocker):
    mock_client = mocker.MagicMock()
    service = DuploEcsService(mock_client)

    updated_task_definition_revision = "arn:aws:ecs:us-east-1:1234567890:task-definition/target-task-definition:2"

    # wait on service called with invalid target service name
    mock_missing_service = [
        { "EcsServiceName": "not-target-service1" },
        { "EcsServiceName": "not-target-service2" },
        { "EcsServiceName": "not-target-service3" },
    ]

    # wait on service finds target service but struct is mal formed
    mock_malformed = [
        {
            "EcsServiceName": "target-service",
            "AwsEcsService": {}
        },
    ]

    # wait on service continues waiting if primary deployment is complete but task definition revision does not match expected revision
    mock_deployment_stale = [
        {
            "EcsServiceName": "target-service",
            "AwsEcsService": {
                "Deployments": [
                    {
                        "Status": "PRIMARY",
                        "TaskDefinition": "arn:aws:ecs:us-east-1:1234567890:task-definition/target-task-definition:1",
                        "RolloutState": { "Value": "COMPLETE" },
                        "DesiredCount": 1,
                        "RunningCount": 1,
                        "PendingCount": 0,
                        "FailedTasks": 0
                    }
                ]
            }
        },
    ]

    # wait on service finds primary deployment but it is incomplete
    mock_deployment_incomplete = [
        {
            "EcsServiceName": "target-service",
            "AwsEcsService": {
                "Deployments": [
                    {
                        "Status": "PRIMARY",
                        "TaskDefinition": updated_task_definition_revision,
                        "RolloutState": { "Value": "IN_PROGRESS" },
                        "DesiredCount": 1,
                        "RunningCount": 0,
                        "PendingCount": 1,
                        "FailedTasks": 0
                    }
                ]
            }
        },
    ]

    # wait on service finds primary deployment but deployment failed
    mock_deployment_failed = [
        {
            "EcsServiceName": "target-service",
            "AwsEcsService": {
                "Deployments": [
                    {
                        "Status": "PRIMARY",
                        "RolloutState": { "Value": "FAILED" },
                        "TaskDefinition": updated_task_definition_revision,
                        "RolloutStateReason": "Opsie... My bad"
                    }
                ]
            }
        },
    ]

    # wait on service finds primary deployment in complete state
    mock_deployment_succeeded = [
        {
            "EcsServiceName": "target-service",
            "AwsEcsService": {
                "Deployments": [
                    {
                        "Status": "PRIMARY",
                        "RolloutState": { "Value": "COMPLETED" },
                        "TaskDefinition": updated_task_definition_revision,
                        "RolloutStateReason": "ECS deployment ecs-svc/8289837686899327606 completed."
                    }
                ]
            }
        },
    ]

    # ECS rolled back: PRIMARY is now the old task definition (rollback), target deployment is FAILED and demoted
    mock_deployment_rollback_failed = [
        {
            "EcsServiceName": "target-service",
            "AwsEcsService": {
                "Deployments": [
                    {
                        "Status": "PRIMARY",
                        "RolloutState": { "Value": "COMPLETED" },
                        "TaskDefinition": "arn:aws:ecs:us-east-1:1234567890:task-definition/target-task-definition:1",
                        "RolloutStateReason": "ECS deployment ecs-svc/1234567890123456789 completed."
                    },
                    {
                        "Status": "ACTIVE",
                        "RolloutState": { "Value": "FAILED" },
                        "TaskDefinition": updated_task_definition_revision,
                        "RolloutStateReason": "ECS deployment circuit breaker: tasks failed to start."
                    }
                ]
            }
        },
    ]

    # ECS rolled back: target demoted from PRIMARY but RolloutState is not yet FAILED
    mock_deployment_rollback_demoted = [
        {
            "EcsServiceName": "target-service",
            "AwsEcsService": {
                "Deployments": [
                    {
                        "Status": "PRIMARY",
                        "RolloutState": { "Value": "COMPLETED" },
                        "TaskDefinition": "arn:aws:ecs:us-east-1:1234567890:task-definition/target-task-definition:1",
                        "RolloutStateReason": "ECS deployment ecs-svc/1234567890123456789 completed."
                    },
                    {
                        "Status": "ACTIVE",
                        "RolloutState": { "Value": "IN_PROGRESS" },
                        "TaskDefinition": updated_task_definition_revision,
                        "RolloutStateReason": "ECS deployment ecs-svc/9876543210987654321 in progress."
                    }
                ]
            }
        },
    ]

    # Deployment stalled: PRIMARY is target but tasks keep failing with none running
    mock_deployment_stalled = [
        {
            "EcsServiceName": "target-service",
            "AwsEcsService": {
                "Deployments": [
                    {
                        "Status": "PRIMARY",
                        "RolloutState": { "Value": "IN_PROGRESS" },
                        "TaskDefinition": updated_task_definition_revision,
                        "RolloutStateReason": "ECS deployment ecs-svc/1003416065081254639 in progress.",
                        "DesiredCount": 1,
                        "RunningCount": 0,
                        "PendingCount": 0,
                        "FailedTasks": 3
                    },
                    {
                        "Status": "ACTIVE",
                        "RolloutState": { "Value": "COMPLETED" },
                        "TaskDefinition": "arn:aws:ecs:us-east-1:1234567890:task-definition/target-task-definition:1",
                        "DesiredCount": 1,
                        "RunningCount": 1,
                        "PendingCount": 0,
                        "FailedTasks": 0
                    }
                ]
            }
        },
    ]

    # Deployment stalled without target_definition_arn (apply flow)
    mock_deployment_stalled_no_target = [
        {
            "EcsServiceName": "target-service",
            "AwsEcsService": {
                "Deployments": [
                    {
                        "Status": "PRIMARY",
                        "RolloutState": { "Value": "IN_PROGRESS" },
                        "TaskDefinition": updated_task_definition_revision,
                        "DesiredCount": 1,
                        "RunningCount": 0,
                        "PendingCount": 0,
                        "FailedTasks": 2
                    }
                ]
            }
        },
    ]

    mocker.patch.object(service, "list_detailed_services", side_effect=[
        mock_missing_service,
        mock_malformed,
        mock_deployment_stale,
        mock_deployment_stale,
        mock_deployment_incomplete,
        mock_deployment_failed,
        mock_deployment_succeeded,
        mock_deployment_rollback_failed,
        mock_deployment_rollback_demoted,
        mock_deployment_stalled,
        mock_deployment_stalled_no_target,
    ])

    # catches wait for cases when target service is not found
    with pytest.raises(DuploError, match=r"Unable to find ECS service"):
        service._wait_on_service("target-service", updated_task_definition_revision)

    # no PRIMARY deployment yet (empty Deployments list, e.g. freshly created service) —
    # transient state, should keep waiting rather than hard-fail
    with pytest.raises(DuploStillWaiting, match=r"Waiting for primary deployment"):
        service._wait_on_service("target-service", updated_task_definition_revision)

    # succeeds even if deployment is stale if no target task definition revision is defined
    service._wait_on_service("target-service")

    # catches wait for cases when service primary is still from and older task definition revision
    with pytest.raises(DuploStillWaiting):
        service._wait_on_service("target-service", updated_task_definition_revision)

    # catches wait for cases when service primary deployment is in progress
    with pytest.raises(DuploStillWaiting):
        service._wait_on_service("target-service", updated_task_definition_revision)

    # catches wait for cases when target service primary deployment fails
    with pytest.raises(DuploError, match=r"deployment failed with reason"):
        service._wait_on_service("target-service", updated_task_definition_revision)

    # passes if service found with primary deployment in complete state
    service._wait_on_service("target-service", updated_task_definition_revision)

    # detects rollback: target deployment FAILED via RolloutState
    with pytest.raises(DuploError, match=r"deployment failed with reason"):
        service._wait_on_service("target-service", updated_task_definition_revision)

    # detects rollback: target demoted from PRIMARY (even without FAILED RolloutState)
    with pytest.raises(DuploError, match=r"deployment rolled back"):
        service._wait_on_service("target-service", updated_task_definition_revision)

    # detects stalled deployment: tasks failing with none running (with target)
    with pytest.raises(DuploError, match=r"deployment stalled"):
        service._wait_on_service("target-service", updated_task_definition_revision)

    # detects stalled deployment via primary check (apply flow, no target)
    with pytest.raises(DuploError, match=r"deployment stalled"):
        service._wait_on_service("target-service")
