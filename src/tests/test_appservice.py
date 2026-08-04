import pytest
from duplocloud.errors import DuploError, DuploNotFound
from duplo_resource.appservice import DuploAppService


_WORKSPACE_ID = "6a0db3da984d2b398701bca7"
_WORKSPACE_NAME = "platform"
_ENV_ID = "8c2fd5fc106f4d5ba923dec9"
_RG_ID = "9d3ae60d217e5e6cba34efd0"
_APPSVC_ID = "7b1ec4eb095e3c4a9812cdb8"
_APPSVC_NAME = "web"


def _make_appservice(mocker, workspace_id=_WORKSPACE_ID):
    """Create a DuploAppService with mocked client + sibling resources.

    ``duplo.load(name)`` returns a distinct, stable mock per name so the
    workspace/environment/resource_group lookups can be configured and
    asserted independently.
    """
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = False
    mock_duplo.host = "https://example.duplocloud.net"
    mock_duplo.timeout = 30
    mock_duplo.workspace = _WORKSPACE_NAME
    mock_duplo.workspaceid = None
    services = {}

    def _load(name):
        return services.setdefault(name, mocker.MagicMock())

    mock_duplo.load.side_effect = _load
    svc = DuploAppService(mock_duplo)
    svc._workspace_id = workspace_id
    svc.duplo.load("workspace").find.return_value = {
        "id": _WORKSPACE_ID, "name": _WORKSPACE_NAME}
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


# List entries carry the env/resource-group ids under spec — update/delete
# read them from there to build the nested route.
_LIST_RESPONSE = {
    "success": True,
    "data": {
        "items": [
            {
                "id": _APPSVC_ID,
                "name": _APPSVC_NAME,
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
    "data": {"id": _APPSVC_ID, "name": _APPSVC_NAME},
}


@pytest.mark.unit
def test_list_unwraps_envelope(mocker):
    svc = _make_appservice(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    result = svc.list()

    assert result == _LIST_RESPONSE["data"]["items"]
    assert client.get.call_args[0][0].endswith(
        f"/workspaces/{_WORKSPACE_ID}/environment/appservices")


@pytest.mark.unit
def test_workspace_resolved_lazily_from_global_flag(mocker):
    svc = _make_appservice(mocker, workspace_id=None)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    svc.list()

    svc.workspace_svc.find.assert_called_once_with(
        name=_WORKSPACE_NAME, id=None)
    assert client.get.call_args[0][0].endswith(
        f"/workspaces/{_WORKSPACE_ID}/environment/appservices")


@pytest.mark.unit
def test_find_by_name_case_insensitive(mocker):
    svc = _make_appservice(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    result = svc.find(name="WEB")

    assert result["id"] == _APPSVC_ID
    assert "filters[name]=WEB" in client.get.call_args[0][0]


@pytest.mark.unit
def test_find_by_id_hits_endpoint_directly(mocker):
    svc = _make_appservice(mocker)
    client = _make_client(mocker, svc, get_responses=[_DETAIL_RESPONSE])

    result = svc.find(id=_APPSVC_ID)

    assert result["id"] == _APPSVC_ID
    assert client.get.call_args[0][0].endswith(f"/appservices/{_APPSVC_ID}")


@pytest.mark.unit
def test_find_requires_name_or_id(mocker):
    svc = _make_appservice(mocker)
    _make_client(mocker, svc, get_responses=[])

    with pytest.raises(DuploError, match="name or --id"):
        svc.find()


@pytest.mark.unit
def test_find_by_name_not_found(mocker):
    svc = _make_appservice(mocker)
    empty = {"success": True, "data": {"items": []}}
    _make_client(mocker, svc, get_responses=[empty])

    with pytest.raises(DuploNotFound):
        svc.find(name="nope")


@pytest.mark.unit
def test_create_posts_to_nested_endpoint(mocker):
    svc = _make_appservice(mocker)
    svc.duplo.load("environment").find.return_value = {"id": _ENV_ID}
    svc.duplo.load("resource_group").find.return_value = {"id": _RG_ID}
    client = _make_client(mocker, svc, get_responses=[])
    client.post.return_value.json.return_value = _DETAIL_RESPONSE

    result = svc.create(
        body={"name": _APPSVC_NAME, "spec": {}},
        environment="dev", resource_group="web")

    client.post.assert_called_once()
    url, body = client.post.call_args[0]
    assert url.endswith(
        f"/environments/{_ENV_ID}/resource-groups/{_RG_ID}/appservices")
    assert body == {"name": _APPSVC_NAME, "spec": {}}
    assert result["id"] == _APPSVC_ID


@pytest.mark.unit
def test_create_requires_body(mocker):
    svc = _make_appservice(mocker)
    _make_client(mocker, svc, get_responses=[])

    with pytest.raises(DuploError, match="body"):
        svc.create(body=None)


@pytest.mark.unit
def test_update_puts_to_nested_endpoint_with_id(mocker):
    svc = _make_appservice(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])
    client.put.return_value.json.return_value = _DETAIL_RESPONSE

    result = svc.update(body={"name": _APPSVC_NAME, "spec": {"x": 1}})

    client.put.assert_called_once()
    url, body = client.put.call_args[0]
    assert url.endswith(
        f"/environments/{_ENV_ID}/resource-groups/{_RG_ID}"
        f"/appservices/{_APPSVC_ID}")
    # id injected so the backend excludes self from name-uniqueness check.
    assert body["id"] == _APPSVC_ID
    assert result["id"] == _APPSVC_ID


@pytest.mark.unit
def test_update_requires_body(mocker):
    svc = _make_appservice(mocker)
    _make_client(mocker, svc, get_responses=[])

    with pytest.raises(DuploError, match="body"):
        svc.update(name=_APPSVC_NAME)


@pytest.mark.unit
def test_delete_posts_deprovision(mocker):
    svc = _make_appservice(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    result = svc.delete(name=_APPSVC_NAME)

    client.post.assert_called_once()
    assert client.post.call_args[0][0].endswith(
        f"/appservices/{_APPSVC_ID}/deprovision")
    assert "deprovision" in result["message"]


@pytest.mark.unit
def test_apply_updates_when_found(mocker):
    svc = _make_appservice(mocker)
    client = _make_client(mocker, svc,
                          get_responses=[_LIST_RESPONSE, _LIST_RESPONSE])
    client.put.return_value.json.return_value = _DETAIL_RESPONSE

    result = svc.apply(body={"name": _APPSVC_NAME, "spec": {}})

    client.put.assert_called_once()
    client.post.assert_not_called()
    assert result["id"] == _APPSVC_ID


@pytest.mark.unit
def test_apply_creates_when_not_found(mocker):
    svc = _make_appservice(mocker)
    svc.duplo.load("environment").find.return_value = {"id": _ENV_ID}
    svc.duplo.load("resource_group").find.return_value = {"id": _RG_ID}
    empty = {"success": True, "data": {"items": []}}
    client = _make_client(mocker, svc, get_responses=[empty])
    client.post.return_value.json.return_value = _DETAIL_RESPONSE

    result = svc.apply(
        body={"name": "brand-new", "spec": {}},
        environment="dev", resource_group="web")

    client.post.assert_called_once()
    client.put.assert_not_called()
    assert result["id"] == _APPSVC_ID


@pytest.mark.unit
def test_apply_requires_name(mocker):
    svc = _make_appservice(mocker)
    _make_client(mocker, svc, get_responses=[])

    with pytest.raises(DuploError, match="name"):
        svc.apply(body={"spec": {}})


@pytest.mark.unit
def test_create_resolves_pascal_case_ids(mocker):
    svc = _make_appservice(mocker)
    # sibling find() results may carry `Id` instead of `id`
    svc.duplo.load("environment").find.return_value = {"Id": _ENV_ID}
    svc.duplo.load("resource_group").find.return_value = {"Id": _RG_ID}
    client = _make_client(mocker, svc, get_responses=[])
    client.post.return_value.json.return_value = _DETAIL_RESPONSE

    svc.create(
        body={"name": _APPSVC_NAME, "spec": {}},
        environment="dev", resource_group="web")

    url = client.post.call_args[0][0]
    assert f"/workspaces/{_WORKSPACE_ID}/environments/{_ENV_ID}" in url
    assert f"/resource-groups/{_RG_ID}/appservices" in url


@pytest.mark.unit
def test_update_image_posts_to_endpoint(mocker):
    svc = _make_appservice(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])
    client.post.return_value.json.return_value = _DETAIL_RESPONSE

    result = svc.update_image(name=_APPSVC_NAME, image="nginx:1.27")

    client.post.assert_called_once()
    url, body = client.post.call_args[0]
    assert url.endswith(f"/appservices/{_APPSVC_ID}/update-image")
    assert body == {"image": "nginx:1.27"}
    assert result["id"] == _APPSVC_ID


@pytest.mark.unit
def test_update_image_requires_image(mocker):
    svc = _make_appservice(mocker)
    _make_client(mocker, svc, get_responses=[])

    with pytest.raises(DuploError, match="image is required"):
        svc.update_image(name=_APPSVC_NAME, image="")
