import json
from datetime import datetime, timezone

import pytest

from duplo_resource.service import DuploService
from duplo_resource.service_rollout import RolloutBaseline
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


T0 = datetime(2026, 11, 18, 20, 0, 0, tzinfo=timezone.utc)
DATE = {"Date": "Wed, 18 Nov 2026 20:00:00 GMT"}


def pod(rs):
  return {
    "Name": "widget",
    "ControlledBy": {
      "NativeId": rs, "QualifiedType": "kubernetes:apps/v1/ReplicaSet"},
  }


def make_waiting(mocker, platform=7, rs=("rs-old",)):
  """A service with wait on, pods() and _wait mocked."""
  svc, mock_client = make_service(mocker, platform=platform)
  mock_client.wait = True
  mocker.patch.object(svc, 'pods', return_value=[pod(r) for r in rs])
  mocker.patch.object(svc, '_wait')
  mock_client.put.return_value.json.return_value = service_body(
    'widget', 'widget:v1', platform)
  mock_client.put.return_value.headers = DATE
  mock_client.post.return_value.headers = DATE
  return svc, mock_client


@pytest.mark.unit
def test_update_image_baseline_taken_before_put(mocker):
  """The ReplicaSets are read before the request and the time comes from its response."""
  svc, mock_client = make_waiting(mocker)
  calls = mocker.Mock()
  calls.attach_mock(svc.pods, 'pods')
  calls.attach_mock(mock_client.put, 'put')
  svc.update_image('widget', 'widget:v1')
  assert [c[0] for c in calls.mock_calls][:2] == ['pods', 'put']
  baseline = svc._wait.call_args.kwargs['baseline']
  assert baseline == RolloutBaseline(frozenset({'rs-old'}), T0)


@pytest.mark.unit
def test_update_image_v2_takes_baseline(mocker):
  """The non-EKS V2 path takes a baseline before its post."""
  svc, mock_client = make_waiting(mocker, platform=0)
  calls = mocker.Mock()
  calls.attach_mock(svc.pods, 'pods')
  calls.attach_mock(mock_client.post, 'post')
  svc.update_image('widget', 'widget:v1')
  assert [c[0] for c in calls.mock_calls][:2] == ['pods', 'post']
  assert svc._wait.call_args.kwargs['baseline'] == RolloutBaseline(
    frozenset({'rs-old'}), T0)


@pytest.mark.unit
def test_update_image_v2_fallback_takes_baseline(mocker):
  """A 404 from V3 falls back to V2, which takes its own baseline."""
  svc, mock_client = make_waiting(mocker)
  mock_client.put.side_effect = DuploNotFound('containerimage')
  svc.update_image('widget', 'widget:v1')
  assert svc._wait.call_args.kwargs['baseline'] == RolloutBaseline(
    frozenset({'rs-old'}), T0)


@pytest.mark.unit
def test_bulk_update_image_baseline_per_service(mocker):
  """Each service gets its own ReplicaSets and the shared bulk response time."""
  svc, mock_client = make_waiting(mocker)
  mocker.patch.object(
    svc, 'pods', side_effect=[[pod('rs-a')], [pod('rs-b')]])
  svc.bulk_update_image([('a', 'a:1'), ('b', 'b:1')])
  baselines = [c.kwargs['baseline'] for c in svc._wait.call_args_list]
  assert baselines == [
    RolloutBaseline(frozenset({'rs-a'}), T0),
    RolloutBaseline(frozenset({'rs-b'}), T0),
  ]


@pytest.mark.unit
def test_restart_waits_for_rollover(mocker):
  """Restart expects a rollover and carries the baseline."""
  svc, mock_client = make_waiting(mocker)
  calls = mocker.Mock()
  calls.attach_mock(svc.pods, 'pods')
  calls.attach_mock(mock_client.post, 'post')
  svc.restart('widget')
  assert [c[0] for c in calls.mock_calls][:2] == ['pods', 'post']
  assert svc._wait.call_args.kwargs['restart'] is True
  assert svc._wait.call_args.kwargs['baseline'] == RolloutBaseline(
    frozenset({'rs-old'}), T0)


@pytest.mark.unit
def test_update_env_baseline_before_post(mocker):
  """update_env reads pods before posting and no longer uses current_replicaset."""
  svc, mock_client = make_waiting(mocker)
  svc.find.return_value['Template']['OtherDockerConfig'] = '{"Env": []}'
  spy = mocker.patch.object(svc, 'current_replicaset')
  calls = mocker.Mock()
  calls.attach_mock(svc.pods, 'pods')
  calls.attach_mock(mock_client.post, 'post')
  svc.update_env('widget', setvar=[('A', 'b')], strategy='merge', deletevar=None)
  assert [c[0] for c in calls.mock_calls][:2] == ['pods', 'post']
  spy.assert_not_called()
  assert svc._wait.call_args.kwargs['baseline'] == RolloutBaseline(
    frozenset({'rs-old'}), T0)


@pytest.mark.unit
def test_update_pod_label_baseline_before_post(mocker):
  """update_pod_label reads pods before posting and no longer uses current_replicaset."""
  svc, mock_client = make_waiting(mocker)
  svc.find.return_value['Template']['OtherDockerConfig'] = '{"PodLabels": {"a": "1"}}'
  spy = mocker.patch.object(svc, 'current_replicaset')
  calls = mocker.Mock()
  calls.attach_mock(svc.pods, 'pods')
  calls.attach_mock(mock_client.post, 'post')
  svc.update_pod_label('widget', setvar=[('b', '2')], strategy='merge', deletevar=None)
  assert [c[0] for c in calls.mock_calls][:2] == ['pods', 'post']
  spy.assert_not_called()
  assert svc._wait.call_args.kwargs['baseline'] == RolloutBaseline(
    frozenset({'rs-old'}), T0)


@pytest.mark.unit
def test_update_pod_label_merge_without_existing_labels(mocker):
  """merge onto a service with no PodLabels creates them instead of raising TypeError."""
  svc, mock_client = make_waiting(mocker)
  svc.find.return_value['Template']['OtherDockerConfig'] = '{}'
  svc.update_pod_label('widget', setvar=[('team', 'qa')], strategy='merge', deletevar=None)
  payload = mock_client.post.call_args.args[1]
  assert json.loads(payload['OtherDockerConfig'])['PodLabels'] == {'team': 'qa'}


@pytest.mark.unit
def test_update_pod_label_deletevar_missing_label_raises(mocker):
  """deleting a label that is not set raises a DuploError naming it."""
  svc, mock_client = make_waiting(mocker)
  svc.find.return_value['Template']['OtherDockerConfig'] = '{}'
  with pytest.raises(DuploError, match='team'):
    svc.update_pod_label('widget', setvar=None, strategy='merge', deletevar=['team'])


@pytest.mark.unit
def test_update_baseline_replaces_current_replicaset(mocker):
  """update takes the baseline instead of reading the current ReplicaSet."""
  svc, mock_client = make_waiting(mocker)
  spy = mocker.patch.object(svc, 'current_replicaset')
  svc.update('widget', body={'Name': 'widget', 'Template': {}})
  spy.assert_not_called()
  assert svc._wait.call_args.kwargs['baseline'] == RolloutBaseline(
    frozenset({'rs-old'}), T0)


@pytest.mark.unit
def test_no_baseline_without_wait(mocker):
  """Without --wait no pods are read."""
  svc, mock_client = make_waiting(mocker)
  mock_client.wait = False
  svc.update_image('widget', 'widget:v1')
  svc.pods.assert_not_called()
  svc._wait.assert_not_called()
