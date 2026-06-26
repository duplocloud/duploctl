import pytest

from duplo_resource.service import DuploService
from duplocloud.errors import DuploError


invalid_kwargs = [
  {
    'name': 'widget',
  },
  {
    'name': 'widget',
    'image': None,
    'container_image': None,
    'init_container_image': None,
  },
]


@pytest.mark.unit
@pytest.mark.parametrize('invalid_kwargs', invalid_kwargs)
def test_invalid_args_raise_errors(invalid_kwargs, mocker):
  mock_client = mocker.MagicMock()
  mock_client.load_client.return_value = mock_client

  with pytest.raises(DuploError, match='Provide a service image, container images, or init container images.'):
    DuploService(mock_client).update_image(**invalid_kwargs)


post_data_tests = [
  # Update main image only.
  (
    {
      'name': 'widget',
      'image': 'widget:v1'
    },
    [
      {'ContainerName': 'duplo-main-container', 'ImageName': 'widget:v1'},
    ],
  ),

  # Update one additional container.
  (
    {
      'name': 'widget',
      'container_image': [('widget-sidecar', 'widget:v2')]
    },
    [
      {'ContainerName': 'widget-sidecar', 'ImageName': 'widget:v2'},
    ],
  ),

  # Update two additional containers.
  (
    {
      'name': 'widget',
      'container_image': [('widget-sidecar1', 'widget:v2'), ('widget-sidecar2', 'widget:v2')]
    },
    [
      {'ContainerName': 'widget-sidecar1', 'ImageName': 'widget:v2'},
      {'ContainerName': 'widget-sidecar2', 'ImageName': 'widget:v2'},
    ],
  ),

  # Update one init container.
  (
    {
      'name': 'widget',
      'init_container_image': [('widget-init', 'widget:v2')]
    },
    [
      {'ContainerName': 'widget-init', 'ImageName': 'widget:v2'},
    ],
  ),

  # Update two init containers.
  (
    {
      'name': 'widget',
      'init_container_image': [('widget-init1', 'widget:v2'), ('widget-init2', 'widget:v2')]
    },
    [
      {'ContainerName': 'widget-init1', 'ImageName': 'widget:v2'},
      {'ContainerName': 'widget-init2', 'ImageName': 'widget:v2'},
    ],
  ),

  # Mixed: main image + additional container.
  (
    {
      'name': 'widget',
      'image': 'nginx:latest',
      'container_image': [('widget-sidecar', 'widget:v2')]
    },
    [
      {'ContainerName': 'duplo-main-container', 'ImageName': 'nginx:latest'},
      {'ContainerName': 'widget-sidecar', 'ImageName': 'widget:v2'},
    ],
  ),

  # Mixed: main image + init container.
  (
    {
      'name': 'widget',
      'image': 'nginx:latest',
      'init_container_image': [('widget-init', 'widget:v2')]
    },
    [
      {'ContainerName': 'duplo-main-container', 'ImageName': 'nginx:latest'},
      {'ContainerName': 'widget-init', 'ImageName': 'widget:v2'},
    ],
  ),

  # Mixed: additional container + init container.
  (
    {
      'name': 'widget',
      'container_image': [('widget-sidecar', 'widget:v2')],
      'init_container_image': [('widget-init', 'widget:v2')]
    },
    [
      {'ContainerName': 'widget-sidecar', 'ImageName': 'widget:v2'},
      {'ContainerName': 'widget-init', 'ImageName': 'widget:v2'},
    ],
  ),

  # Mixed: all three types.
  (
    {
      'name': 'widget',
      'image': 'nginx:latest',
      'container_image': [('widget-sidecar', 'envoy:v1')],
      'init_container_image': [('widget-init', 'busybox:1.36')]
    },
    [
      {'ContainerName': 'duplo-main-container', 'ImageName': 'nginx:latest'},
      {'ContainerName': 'widget-sidecar', 'ImageName': 'envoy:v1'},
      {'ContainerName': 'widget-init', 'ImageName': 'busybox:1.36'},
    ],
  ),
]


@pytest.mark.unit
@pytest.mark.parametrize('kwargs,expected_payload', post_data_tests)
def test_post_data(kwargs, expected_payload, mocker):
  mock_client = mocker.MagicMock()
  mock_client.load_client.return_value = mock_client
  mock_client.wait = False
  svc = DuploService(mock_client)
  svc._tenant_id = 'test-tenant-id'
  svc.update_image(**kwargs)
  name = kwargs['name']
  expected_endpoint = f"v3/subscriptions/test-tenant-id/containers/replicationController/{name}/containerimage"
  mock_client.put.assert_called_once_with(expected_endpoint, expected_payload)
