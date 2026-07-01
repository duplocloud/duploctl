import pytest
from duplocloud.errors import DuploError, DuploNotFound
from duplo_resource.hd_lambda import DuploHelpdeskLambda


_WORKSPACE_ID = "6a0db3da984d2b398701bca7"
_ENV_ID = "8c2fd5fc106f4d5ba923dec9"
_RG_ID = "9d3ae60d217e5e6cba34efd0"
_LAMBDA_ID = "5e191a9d959c41fc8b314ed8"
_LAMBDA_NAME = "worker"


def _make_lambda(mocker):
    """Create a DuploHelpdeskLambda with mocked client + sibling resources.

    ``duplo.load(name)`` returns a distinct, stable mock per name so the
    workspace/environment/resource_group lookups can be configured and
    asserted independently.
    """
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = False
    mock_duplo.host = "https://example.duplocloud.net"
    mock_duplo.timeout = 30
    services = {}

    def _load(name):
        return services.setdefault(name, mocker.MagicMock())

    mock_duplo.load.side_effect = _load
    svc = DuploHelpdeskLambda(mock_duplo)
    svc._tenant = {"AccountName": "myaccount", "TenantId": "tid-123"}
    svc._tenant_id = "tid-123"
    svc.duplo.load("workspace").find.return_value = {
        "id": _WORKSPACE_ID, "name": "platform"}
    return svc


def _make_client(mocker, svc, get_responses):
    """Wire a mock client returning the supplied GET JSON payloads in order."""
    mock_client = mocker.MagicMock()
    get_mocks = [mocker.MagicMock() for _ in get_responses]
    for m, payload in zip(get_mocks, get_responses):
        m.json.return_value = payload
    mock_client.get.side_effect = get_mocks
    mocker.patch.object(svc, "client", mock_client)
    return mock_client


# List entries carry the env/resource-group ids under spec — that is where the
# nested (update/delete/code) routes read them from.
_LIST_RESPONSE = {
    "success": True,
    "data": {
        "items": [
            {
                "id": _LAMBDA_ID,
                "name": _LAMBDA_NAME,
                "spec": {
                    "environmentId": _ENV_ID,
                    "resourceGroupId": _RG_ID,
                },
            },
            {"id": "other-id", "name": "other", "spec": {}},
        ],
    },
}

_DETAIL_RESPONSE = {
    "success": True,
    "data": {"id": _LAMBDA_ID, "name": _LAMBDA_NAME},
}


@pytest.mark.unit
def test_list_unwraps_envelope(mocker):
    svc = _make_lambda(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    result = svc.list(workspace="platform")

    assert result == _LIST_RESPONSE["data"]["items"]
    assert client.get.call_args[0][0].endswith(
        f"/workspaces/{_WORKSPACE_ID}/environment/AwsLambdas")


@pytest.mark.unit
def test_find_by_name_case_insensitive(mocker):
    svc = _make_lambda(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    result = svc.find(name="WORKER", workspace="platform")

    assert result["id"] == _LAMBDA_ID
    assert "filters[name]=WORKER" in client.get.call_args[0][0]


@pytest.mark.unit
def test_find_requires_name_or_id(mocker):
    svc = _make_lambda(mocker)
    _make_client(mocker, svc, get_responses=[])

    with pytest.raises(DuploError, match="name or --id"):
        svc.find(workspace="platform")


@pytest.mark.unit
def test_create_posts_to_nested_endpoint(mocker):
    svc = _make_lambda(mocker)
    svc.duplo.load("environment").find.return_value = {"id": _ENV_ID}
    svc.duplo.load("resource_group").find.return_value = {"id": _RG_ID}
    client = _make_client(mocker, svc, get_responses=[])
    client.post.return_value.json.return_value = _DETAIL_RESPONSE

    result = svc.create(
        body={"name": _LAMBDA_NAME, "spec": {}},
        environment="dev", resource_group="web", workspace="platform")

    client.post.assert_called_once()
    url, body = client.post.call_args[0]
    assert url.endswith(
        f"/environments/{_ENV_ID}/resource-groups/{_RG_ID}/AwsLambdas")
    assert result["id"] == _LAMBDA_ID


@pytest.mark.unit
def test_update_puts_to_nested_endpoint_with_id(mocker):
    svc = _make_lambda(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])
    client.put.return_value.json.return_value = _DETAIL_RESPONSE

    result = svc.update(
        body={"name": _LAMBDA_NAME, "spec": {"x": 1}}, workspace="platform")

    client.put.assert_called_once()
    url, body = client.put.call_args[0]
    assert url.endswith(
        f"/environments/{_ENV_ID}/resource-groups/{_RG_ID}"
        f"/AwsLambdas/{_LAMBDA_ID}")
    assert body["id"] == _LAMBDA_ID
    assert result["id"] == _LAMBDA_ID


@pytest.mark.unit
def test_delete_posts_deprovision(mocker):
    svc = _make_lambda(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    result = svc.delete(name=_LAMBDA_NAME, workspace="platform")

    client.post.assert_called_once()
    assert client.post.call_args[0][0].endswith(
        f"/AwsLambdas/{_LAMBDA_ID}/deprovision")
    assert "deprovision" in result["message"]


@pytest.mark.unit
def test_apply_creates_when_not_found(mocker):
    svc = _make_lambda(mocker)
    svc.duplo.load("environment").find.return_value = {"id": _ENV_ID}
    svc.duplo.load("resource_group").find.return_value = {"id": _RG_ID}
    empty = {"success": True, "data": {"items": []}}
    client = _make_client(mocker, svc, get_responses=[empty])
    client.post.return_value.json.return_value = _DETAIL_RESPONSE

    result = svc.apply(
        body={"name": "brand-new", "spec": {}},
        environment="dev", resource_group="web", workspace="platform")

    client.post.assert_called_once()
    client.put.assert_not_called()
    assert result["id"] == _LAMBDA_ID


@pytest.mark.unit
def test_update_image_posts_to_nested_code_endpoint(mocker):
    svc = _make_lambda(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])
    client.post.return_value.json.return_value = _DETAIL_RESPONSE

    result = svc.update_image(
        name=_LAMBDA_NAME, image="123.dkr.ecr/img:tag", workspace="platform")

    client.post.assert_called_once()
    url, body = client.post.call_args[0]
    assert url.endswith(
        f"/environments/{_ENV_ID}/resource-groups/{_RG_ID}"
        f"/AwsLambdas/{_LAMBDA_ID}/code")
    assert body == {"ImageUri": "123.dkr.ecr/img:tag"}
    assert result["id"] == _LAMBDA_ID


@pytest.mark.unit
def test_update_image_requires_image(mocker):
    svc = _make_lambda(mocker)
    _make_client(mocker, svc, get_responses=[])

    with pytest.raises(DuploError, match="image is required"):
        svc.update_image(name=_LAMBDA_NAME, image="", workspace="platform")


@pytest.mark.unit
def test_update_image_missing_env_or_rg_raises(mocker):
    svc = _make_lambda(mocker)
    # a function whose spec is missing the env/rg ids cannot build the route
    bad_list = {
        "success": True,
        "data": {"items": [{"id": _LAMBDA_ID, "name": _LAMBDA_NAME,
                            "spec": {}}]},
    }
    _make_client(mocker, svc, get_responses=[bad_list])

    with pytest.raises(DuploError, match="environment/resource-group"):
        svc.update_image(
            name=_LAMBDA_NAME, image="img:tag", workspace="platform")
