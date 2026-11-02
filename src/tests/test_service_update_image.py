import pytest

from duplo_resource.service import DuploService
from duplocloud.errors import DuploError, DuploNotFound


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


def service_body(name: str, image: str, platform: int) -> dict:
  """Build a minimal service body as returned by find and the V3 PUT."""
  return {
    'Name': name,
    'Template': {
      'AgentPlatform': platform,
      'AllocationTags': '',
      'Containers': [{'Name': name, 'Image': image}],
    },
  }


def make_service(mocker, platform: int, image: str = 'widget:v0'):
  """Create a DuploService whose find returns a service on the platform."""
  mock_client = mocker.MagicMock()
  mock_client.load_client.return_value = mock_client
  mock_client.wait = False
  svc = DuploService(mock_client)
  svc._tenant_id = 'test-tenant-id'
  mocker.patch.object(
    svc, 'find', return_value=service_body('widget', image, platform))
  return svc, mock_client


V3_ENDPOINT = ("v3/subscriptions/test-tenant-id/containers/"
               "replicationController/widget/containerimage")


@pytest.mark.unit
@pytest.mark.parametrize('kwargs,expected_payload', post_data_tests)
def test_post_data(kwargs, expected_payload, mocker):
  """EKS services send every image to the V3 containerimage endpoint."""
  svc, mock_client = make_service(mocker, platform=7)
  mock_client.put.return_value.json.return_value = service_body(
    'widget', kwargs.get('image') or 'widget:v0', 7)
  svc.update_image(**kwargs)
  mock_client.put.assert_called_once_with(V3_ENDPOINT, expected_payload)
  mock_client.post.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize('platform', [0, 6])
def test_non_eks_uses_v2(platform, mocker):
  """Non-EKS services skip V3, which ignores the image off EKS."""
  svc, mock_client = make_service(mocker, platform=platform)
  svc.update_image('widget', image='widget:v1')
  mock_client.put.assert_not_called()
  mock_client.post.assert_called_once_with(
    'subscriptions/test-tenant-id/ReplicationControllerChange',
    {'Name': 'widget', 'Image': 'widget:v1', 'AllocationTags': ''})


@pytest.mark.unit
@pytest.mark.parametrize('kwargs', [
  {'container_image': [('widget-sidecar', 'envoy:v1')]},
  {'image': 'widget:v1', 'init_container_image': [('widget-init', 'b:1')]},
])
def test_non_eks_sidecars_raise(kwargs, mocker):
  """Sidecar and init images on non-EKS services fail instead of no-op."""
  svc, mock_client = make_service(mocker, platform=0)
  with pytest.raises(DuploError, match='only supported for EKS services'):
    svc.update_image('widget', **kwargs)
  mock_client.put.assert_not_called()
  mock_client.post.assert_not_called()


@pytest.mark.unit
def test_eks_unchanged_image_raises(mocker):
  """A 2xx from V3 that leaves the main image unchanged is an error."""
  svc, mock_client = make_service(mocker, platform=7)
  mock_client.put.return_value.json.return_value = service_body(
    'widget', 'widget:v0', 7)
  with pytest.raises(DuploError, match="main image is 'widget:v0'"):
    svc.update_image('widget', image='widget:v1')


@pytest.mark.unit
def test_eks_404_main_image_falls_back_to_v2(mocker):
  """Older backends without the V3 route fall back to V2."""
  svc, mock_client = make_service(mocker, platform=7)
  mock_client.put.side_effect = DuploNotFound('containerimage')
  svc.update_image('widget', image='widget:v1')
  mock_client.post.assert_called_once_with(
    'subscriptions/test-tenant-id/ReplicationControllerChange',
    {'Name': 'widget', 'Image': 'widget:v1', 'AllocationTags': ''})


@pytest.mark.unit
def test_eks_404_sidecar_raises_without_v2(mocker):
  """An unknown sidecar name surfaces the 404 instead of falling back."""
  svc, mock_client = make_service(mocker, platform=7)
  mock_client.put.side_effect = DuploNotFound(
    '{"Message":"One or more Init / Additional Containers could not be found"}')
  with pytest.raises(DuploError) as err:
    svc.update_image('widget', container_image=[('typo', 'envoy:v1')])
  assert str(err.value) == (
    "Failed to update container images for service 'widget': "
    "One or more Init / Additional Containers could not be found")
  mock_client.post.assert_not_called()
