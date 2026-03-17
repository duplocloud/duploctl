import json
from unittest.mock import ANY

import pytest

from duplo_resource.service import DuploService
from duplocloud.errors import DuploError


invalid_kwargs = [
  {
    'name': 'widget',
  },
]


@pytest.mark.unit
@pytest.mark.parametrize('invalid_kwargs', invalid_kwargs)
def test_invalid_args_raise_errors(invalid_kwargs, mocker):
  mock_client = mocker.MagicMock()
  mock_client.load_client.return_value = mock_client

  # DuploError is generic. It doesn't specifically identify bad input. We have to match the error message or we
  # can get false positives if the method raises a DuploError later about something else.
  with pytest.raises(DuploError, match='Provide a service image, container images, or init container images.'):
    DuploService(mock_client).update_image(**invalid_kwargs)


no_matching_container_tests = [
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'additionalContainers': [
        {
          'name': 'widget-sidecar',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'container_image': [('not-widget-sidecar', 'widget:v2')]
    }
  ),
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'initContainers': [
        {
          'name': 'widget-init',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'init_container_image': [('not-widget-init', 'widget:v2')]
    }
  )
]


@pytest.mark.unit
@pytest.mark.parametrize('service_definition,kwargs', no_matching_container_tests)
def test_no_matching_container_raises_error(service_definition, kwargs, mocker):
  mocker.patch(
    'duplo_resource.service.DuploService.find',
    mocker.MagicMock(return_value=service_definition)
  )
  mock_client = mocker.MagicMock()
  mock_client.load_client.return_value = mock_client

  # DuploError is generic. It doesn't specifically identify bad input. We have to match the error message or we
  # can get false positives if the method raises a DuploError later about something else.
  with pytest.raises(DuploError, match=r'No matching containers found in service .*'):
    DuploService(mock_client).update_image(**kwargs)


put_data_tests = [
  # Update one service.
  (
    {'Template': {}},
    {
      'name': 'widget',
      'image': 'widget:v1'
    },
    [{"ContainerName": "widget", "ImageName": "widget:v1"}],
  ),

  # Update one additional container.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'additionalContainers': [
        {
          'name': 'widget-sidecar',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'container_image': [('widget-sidecar', 'widget:v2')]
    },
    [{"ContainerName": "widget-sidecar", "ImageName": "widget:v2"}],
  ),

  # Update first of two additional containers.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'additionalContainers': [
        {
          'name': 'widget-sidecar1',
          'image': 'widget:v1',
        },
        {
          'name': 'widget-sidecar2',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'container_image': [('widget-sidecar1', 'widget:v2')]
    },
    [{"ContainerName": "widget-sidecar1", "ImageName": "widget:v2"}],
  ),

  # Update second of two additional containers.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'additionalContainers': [
        {
          'name': 'widget-sidecar1',
          'image': 'widget:v1',
        },
        {
          'name': 'widget-sidecar2',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'container_image': [('widget-sidecar2', 'widget:v2')]
    },
    [{"ContainerName": "widget-sidecar2", "ImageName": "widget:v2"}],
  ),

  # Update two of two additional containers.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'additionalContainers': [
        {
          'name': 'widget-sidecar1',
          'image': 'widget:v1',
        },
        {
          'name': 'widget-sidecar2',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'container_image': [('widget-sidecar1', 'widget:v2'), ('widget-sidecar2', 'widget:v2')]
    },
    [
      {"ContainerName": "widget-sidecar1", "ImageName": "widget:v2"},
      {"ContainerName": "widget-sidecar2", "ImageName": "widget:v2"},
    ],
  ),

  # Update two of one additional containers.
  # Arguably, trying to update images for two additional containers in a service that only has one additional container
  # should raise an error. This test was written to assert existing behavior to preserve backwards compatibility.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'additionalContainers': [
        {
          'name': 'widget-sidecar2',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'container_image': [('widget-sidecar1', 'widget:v2'), ('widget-sidecar2', 'widget:v2')]
    },
    [{"ContainerName": "widget-sidecar2", "ImageName": "widget:v2"}],
  ),

  # Update one init container.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'initContainers': [
        {
          'name': 'widget-init',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'init_container_image': [('widget-init', 'widget:v2')]
    },
    [{"ContainerName": "widget-init", "ImageName": "widget:v2"}],
  ),

  # Update first of two init containers.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'initContainers': [
        {
          'name': 'widget-init1',
          'image': 'widget:v1',
        },
        {
          'name': 'widget-init2',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'init_container_image': [('widget-init1', 'widget:v2')]
    },
    [{"ContainerName": "widget-init1", "ImageName": "widget:v2"}],
  ),

  # Update second of two init containers.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'initContainers': [
        {
          'name': 'widget-init1',
          'image': 'widget:v1',
        },
        {
          'name': 'widget-init2',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'init_container_image': [('widget-init2', 'widget:v2')]
    },
    [{"ContainerName": "widget-init2", "ImageName": "widget:v2"}],
  ),

  # Update two of two init containers.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'initContainers': [
        {
          'name': 'widget-init1',
          'image': 'widget:v1',
        },
        {
          'name': 'widget-init2',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'init_container_image': [('widget-init1', 'widget:v2'), ('widget-init2', 'widget:v2')]
    },
    [
      {"ContainerName": "widget-init1", "ImageName": "widget:v2"},
      {"ContainerName": "widget-init2", "ImageName": "widget:v2"},
    ],
  ),

  # Update two of one init containers.
  # Arguably, trying to update images for two init containers in a service that only has one init container should
  # raise an error. When init containers were added, support for additional containers already existed and it allowed
  # this case. Because images for additional containers and init containers work the same, support for init containers
  # followed the pattern set for additional containers.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'initContainers': [
        {
          'name': 'widget-init2',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'init_container_image': [('widget-init1', 'widget:v2'), ('widget-init2', 'widget:v2')]
    },
    [{"ContainerName": "widget-init2", "ImageName": "widget:v2"}],
  ),
]


@pytest.mark.unit
@pytest.mark.parametrize('service_definition,kwargs,put_data', put_data_tests)
def test_put_data(service_definition, kwargs, put_data, mocker):
  service = service_definition
  mocker.patch(
    'duplo_resource.service.DuploService.find',
    mocker.MagicMock(return_value=service)
  )
  mock_client = mocker.MagicMock()
  mock_client.load_client.return_value = mock_client
  mock_client.wait = False
  DuploService(mock_client).update_image(**kwargs)
  mock_client.put.assert_called_once_with(ANY, put_data)


combined_update_tests = [
  # Update main image and one sidecar container.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'additionalContainers': [
        {
          'name': 'widget-sidecar',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'image': 'nginx:latest',
      'container_image': [('widget-sidecar', 'widget:v2')]
    },
    [
      {"ContainerName": "widget", "ImageName": "nginx:latest"},
      {"ContainerName": "widget-sidecar", "ImageName": "widget:v2"},
    ],
  ),

  # Update main image and one init container.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({'initContainers': [
        {
          'name': 'widget-init',
          'image': 'widget:v1',
        }
      ]})}
    },
    {
      'name': 'widget',
      'image': 'nginx:latest',
      'init_container_image': [('widget-init', 'widget:v2')]
    },
    [
      {"ContainerName": "widget", "ImageName": "nginx:latest"},
      {"ContainerName": "widget-init", "ImageName": "widget:v2"},
    ],
  ),

  # Update sidecar and init containers together.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({
        'additionalContainers': [
          {'name': 'widget-sidecar', 'image': 'widget:v1'}
        ],
        'initContainers': [
          {'name': 'widget-init', 'image': 'widget:v1'}
        ]
      })}
    },
    {
      'name': 'widget',
      'container_image': [('widget-sidecar', 'widget:v2')],
      'init_container_image': [('widget-init', 'widget:v2')]
    },
    [
      {"ContainerName": "widget-sidecar", "ImageName": "widget:v2"},
      {"ContainerName": "widget-init", "ImageName": "widget:v2"},
    ],
  ),

  # Update all three container types at once.
  (
    {
      'Template': {'OtherDockerConfig': json.dumps({
        'additionalContainers': [
          {'name': 'widget-sidecar', 'image': 'widget:v1'}
        ],
        'initContainers': [
          {'name': 'widget-init', 'image': 'widget:v1'}
        ]
      })}
    },
    {
      'name': 'widget',
      'image': 'nginx:latest',
      'container_image': [('widget-sidecar', 'widget:v2')],
      'init_container_image': [('widget-init', 'widget:v2')]
    },
    [
      {"ContainerName": "widget", "ImageName": "nginx:latest"},
      {"ContainerName": "widget-sidecar", "ImageName": "widget:v2"},
      {"ContainerName": "widget-init", "ImageName": "widget:v2"},
    ],
  ),
]


@pytest.mark.unit
@pytest.mark.parametrize('service_definition,kwargs,put_data', combined_update_tests)
def test_combined_update(service_definition, kwargs, put_data, mocker):
  service = service_definition
  mocker.patch(
    'duplo_resource.service.DuploService.find',
    mocker.MagicMock(return_value=service)
  )
  mock_client = mocker.MagicMock()
  mock_client.load_client.return_value = mock_client
  mock_client.wait = False
  DuploService(mock_client).update_image(**kwargs)
  mock_client.put.assert_called_once_with(ANY, put_data)
