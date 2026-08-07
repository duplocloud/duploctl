import pytest
from duplo_resource.helpdesk_client import unwrap_items
from duplocloud.errors import DuploError, DuploNotFound
from duplo_resource.resource_group import DuploResourceGroup


_WORKSPACE_ID = "6a0db3da984d2b398701bca7"
_WORKSPACE_NAME = "platform"
_ENV_ID = "8c2fd5fc106f4d5ba923dec9"
_RG_ID = "9d3ae60d217e5e6cba34efd0"
_RG_NAME = "web"


def _make_resource_group(mocker):
    """Create a DuploResourceGroup with mocked client + sibling resources."""
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
    svc = DuploResourceGroup(mock_duplo)
    svc._workspace_id = _WORKSPACE_ID
    return svc


def _make_client(mocker, svc, get_responses):
    """Wire a mock client returning the supplied GET JSON payloads in order."""
    mock_client = mocker.MagicMock()
    get_mocks = [mocker.MagicMock() for _ in get_responses]
    for m, payload in zip(get_mocks, get_responses):
        m.json.return_value = payload
    mock_client.get.side_effect = get_mocks
    # get_items delegates to the ordered get mocks like the real client
    # (which pages through get), so wired responses serve both.
    mock_client.get_items.side_effect = (
        lambda p: unwrap_items(mock_client.get(p).json()))
    mocker.patch.object(svc, "client", mock_client)
    return mock_client


# Two resource groups share the name "web" across different environments; the
# environment scope is what disambiguates them.
_LIST_RESPONSE = {
    "success": True,
    "data": {
        "items": [
            {"id": _RG_ID, "name": _RG_NAME,
             "spec": {"environmentId": _ENV_ID}},
            {"id": "rg-other", "name": _RG_NAME,
             "spec": {"environmentId": "env-other"}},
        ],
    },
}

_DETAIL_RESPONSE = {
    "success": True,
    "data": {"id": _RG_ID, "name": _RG_NAME},
}


@pytest.mark.unit
def test_list_unwraps_envelope(mocker):
    svc = _make_resource_group(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    result = svc.list()

    assert result == _LIST_RESPONSE["data"]["items"]
    assert client.get.call_args[0][0].endswith(
        f"/workspaces/{_WORKSPACE_ID}/environment/resource-groups")


@pytest.mark.unit
def test_list_scoped_to_environment(mocker):
    svc = _make_resource_group(mocker)
    svc.duplo.load("environment").find.return_value = {"id": _ENV_ID}
    _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    result = svc.list(environment="dev")

    assert [rg["id"] for rg in result] == [_RG_ID]


@pytest.mark.unit
def test_find_by_name_disambiguated_by_environment(mocker):
    svc = _make_resource_group(mocker)
    svc.duplo.load("environment").find.return_value = {"id": _ENV_ID}
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    result = svc.find(name="WEB", environment="dev")

    assert result["id"] == _RG_ID
    assert "filters[name]=WEB" in client.get.call_args[0][0]


@pytest.mark.unit
def test_find_by_id_hits_endpoint_directly(mocker):
    svc = _make_resource_group(mocker)
    client = _make_client(mocker, svc, get_responses=[_DETAIL_RESPONSE])

    result = svc.find(id=_RG_ID)

    assert result["id"] == _RG_ID
    assert client.get.call_args[0][0].endswith(f"/resource-groups/{_RG_ID}")


@pytest.mark.unit
def test_find_requires_name_or_id(mocker):
    svc = _make_resource_group(mocker)
    _make_client(mocker, svc, get_responses=[])

    with pytest.raises(DuploError, match="name or --id"):
        svc.find()


@pytest.mark.unit
def test_find_not_found_when_environment_excludes_match(mocker):
    svc = _make_resource_group(mocker)
    # environment resolves to an id that matches none of the listed groups
    svc.duplo.load("environment").find.return_value = {"id": "env-nomatch"}
    _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])

    with pytest.raises(DuploNotFound):
        svc.find(name=_RG_NAME, environment="ghost")


@pytest.mark.unit
def test_create_posts_to_nested_environment_endpoint(mocker):
    svc = _make_resource_group(mocker)
    svc.duplo.load("environment").find.return_value = {"id": _ENV_ID}
    client = _make_client(mocker, svc, get_responses=[])
    client.post.return_value.json.return_value = _DETAIL_RESPONSE

    result = svc.create(
        body={"name": _RG_NAME, "spec": {"cloud": "K8S_ONLY"}},
        environment="dev")

    client.post.assert_called_once()
    url, body = client.post.call_args[0]
    assert url.endswith(
        f"/environments/{_ENV_ID}/resource-groups")
    assert body["spec"]["cloud"] == "K8S_ONLY"
    assert result["id"] == _RG_ID


@pytest.mark.unit
def test_create_requires_body(mocker):
    svc = _make_resource_group(mocker)
    _make_client(mocker, svc, get_responses=[])

    with pytest.raises(DuploError, match="body"):
        svc.create(body=None, environment="dev")


@pytest.mark.unit
def test_create_strips_scope_ids(mocker):
    # The backend derives scope ids from the parent RG and rejects any
    # caller-supplied value, so a record round-tripped from find must have
    # spec.scopeIds stripped before the POST.
    svc = _make_resource_group(mocker)
    svc.duplo.load("environment").find.return_value = {"id": _ENV_ID}
    client = _make_client(mocker, svc, get_responses=[])
    client.post.return_value.json.return_value = _DETAIL_RESPONSE

    svc.create(
        body={"name": _RG_NAME,
              "spec": {"cloud": "K8S_ONLY", "scopeIds": ["s-1"]}},
        environment="dev")

    body = client.post.call_args[0][1]
    assert "scopeIds" not in body["spec"]
    assert body["spec"]["cloud"] == "K8S_ONLY"


@pytest.mark.unit
def test_update_puts_with_preserved_env(mocker):
    svc = _make_resource_group(mocker)
    client = _make_client(mocker, svc, get_responses=[_LIST_RESPONSE])
    client.put.return_value.json.return_value = _DETAIL_RESPONSE

    result = svc.update(body={"name": _RG_NAME, "spec": {}})

    client.put.assert_called_once()
    url, body = client.put.call_args[0]
    assert url.endswith(f"/resource-groups/{_RG_ID}")
    # environmentId is immutable; the update must carry it forward from the
    # existing record so the backend doesn't read the PUT as nulling it out.
    assert body["spec"]["environmentId"] == _ENV_ID
    assert result["id"] == _RG_ID


@pytest.mark.unit
def test_update_carries_cloud_forward(mocker):
    # spec.cloud is a non-nullable enum server-side: omitted, it deserializes
    # to the default (Aws) and trips the immutable-Cloud check for any
    # non-AWS group — so the update must carry it forward from the record.
    svc = _make_resource_group(mocker)
    listed = {
        "success": True,
        "data": {"items": [
            {"id": _RG_ID, "name": _RG_NAME,
             "spec": {"environmentId": _ENV_ID, "cloud": "K8S_ONLY"}},
        ]},
    }
    client = _make_client(mocker, svc, get_responses=[listed])
    client.put.return_value.json.return_value = _DETAIL_RESPONSE

    svc.update(body={"name": _RG_NAME, "spec": {"description": "x"}})

    body = client.put.call_args[0][1]
    assert body["spec"]["cloud"] == "K8S_ONLY"
    assert body["spec"]["environmentId"] == _ENV_ID


@pytest.mark.unit
def test_update_preserves_pascal_case_spec(mocker):
    svc = _make_resource_group(mocker)
    # the immutable placement must be carried forward even if the existing
    # record's spec uses `EnvironmentId`/`ClusterId` casing
    pascal_list = {
        "success": True,
        "data": {"items": [
            {"id": _RG_ID, "name": _RG_NAME,
             "spec": {"EnvironmentId": _ENV_ID, "ClusterId": "cid-1"}},
        ]},
    }
    client = _make_client(mocker, svc, get_responses=[pascal_list])
    client.put.return_value.json.return_value = _DETAIL_RESPONSE

    svc.update(body={"name": _RG_NAME, "spec": {}})

    _, body = client.put.call_args[0]
    assert body["spec"]["environmentId"] == _ENV_ID
    assert body["spec"]["clusterId"] == "cid-1"


@pytest.mark.unit
def test_apply_requires_name(mocker):
    svc = _make_resource_group(mocker)
    _make_client(mocker, svc, get_responses=[])

    with pytest.raises(DuploError, match="name"):
        svc.apply(body={"spec": {}})


@pytest.mark.unit
def test_delete_plain(mocker):
    svc = _make_resource_group(mocker)
    # delete(id=...) resolves via find(id=...), a direct single-object GET
    client = _make_client(mocker, svc, get_responses=[_DETAIL_RESPONSE])

    result = svc.delete(id=_RG_ID)

    client.delete.assert_called_once()
    assert client.delete.call_args[0][0].endswith(
        f"/resource-groups/{_RG_ID}")
    assert "deleted" in result["message"]


@pytest.mark.unit
def test_deprovision_confirms_all_preview_children(mocker):
    svc = _make_resource_group(mocker)
    # find (by id) then the deprovision-preview list (data is a bare list)
    detail = {"success": True, "data": {"id": _RG_ID, "name": _RG_NAME}}
    preview = {"success": True, "data": [
        {"id": "child-1", "type": "Namespace", "name": "ns"},
        {"id": "child-2", "type": "AwsLambda", "name": "fn"},
    ]}
    client = _make_client(mocker, svc, get_responses=[detail, preview])

    result = svc.deprovision(id=_RG_ID)

    client.post.assert_called_once()
    url, body = client.post.call_args[0]
    assert url.endswith(f"/resource-groups/{_RG_ID}/deprovision")
    assert body == {"selectedResourceIds": ["child-1", "child-2"]}
    assert "2 child" in result["message"]
