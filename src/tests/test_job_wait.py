import pytest

from duplo_resource.job import DuploJob
from duplo_resource.pod import DuploPod
from duplocloud.errors import DuploFailedResource, DuploStillWaiting


def _make_job(mocker, status):
    """Create a DuploJob with a mocked duplo client and a fixed find() status."""
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = True
    mock_duplo.wait_timeout = 3  # keep the wait loop to a single iteration
    job = DuploJob(mock_duplo)
    job._tenant = {"AccountName": "myaccount", "TenantId": "tid-123"}
    job._tenant_id = "tid-123"
    mocker.patch.object(job, "client", mocker.MagicMock())
    mocker.patch.object(job, "find", return_value={
        "status": status,
        "spec": {"completions": 4, "backoffLimit": 6},
    })
    return job


_JOB_BODY = {"metadata": {"name": "duploctl"}}


@pytest.mark.unit
def test_create_succeeds_on_complete_even_without_pods(mocker):
    """A Complete job must succeed even if its pods are gone from the listing."""
    job = _make_job(mocker, status={
        "active": 0, "succeeded": 4, "failed": 0,
        "conditions": [{"type": "Complete", "status": "True"}],
    })
    # completed pods dropped from the listing — this used to spin until timeout
    mocker.patch.object(job, "pods", return_value=[])

    result = job.create(_JOB_BODY)

    assert "ran successfully" in result["message"]


@pytest.mark.unit
def test_create_fails_fast_on_failed_condition(mocker):
    job = _make_job(mocker, status={
        "active": 0, "succeeded": 0, "failed": 4,
        "conditions": [{
            "type": "Failed", "status": "True",
            "reason": "BackoffLimitExceeded", "message": "too many retries",
        }],
    })
    mocker.patch.object(job, "pods", return_value=[])

    with pytest.raises(DuploFailedResource, match="BackoffLimitExceeded"):
        job.create(_JOB_BODY)


@pytest.mark.unit
def test_create_still_waits_while_running(mocker):
    job = _make_job(mocker, status={
        "active": 2, "succeeded": 0, "failed": 0, "conditions": [],
    })
    mocker.patch.object(job, "pods", return_value=[])
    mocker.patch("time.sleep")

    with pytest.raises(DuploStillWaiting):
        job.create(_JOB_BODY)


@pytest.mark.unit
def test_pod_logs_handles_missing_data_key(mocker):
    """findContainerLogs may return no Data key for a pod without logs yet."""
    mock_duplo = mocker.MagicMock()
    pod_svc = DuploPod(mock_duplo)
    pod_svc._tenant = {"AccountName": "myaccount", "TenantId": "tid-123"}
    pod_svc._tenant_id = "tid-123"
    mock_client = mocker.MagicMock()
    mock_client.post.return_value.json.return_value = {}
    mocker.patch.object(pod_svc, "client", mock_client)

    result = pod_svc.logs(pod={
        "CurrentStatus": 1,
        "Host": "host1",
        "InstanceId": "duploctl-abc12",
        "Containers": [{"DockerId": "docker-1"}],
    })

    assert result is None
    mock_client.post.assert_called_once()
