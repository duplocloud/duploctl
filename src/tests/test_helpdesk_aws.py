import pytest
from duplocloud.errors import DuploError
from duplo_resource.helpdesk_aws import DuploAwsCredentials

_WID = "ws-1"

_CREDS = {"accessKeyId": "AKIA123", "secretAccessKey": "sk",
          "sessionToken": "st", "region": "us-east-2",
          "validity": 3600, "expiration": "2026-09-24T13:00:00Z",
          "consoleUrl": "https://signin.aws"}


def _make_resource(mocker):
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = False
    resource = DuploAwsCredentials(mock_duplo)
    mocker.patch.object(type(resource), "workspace_id",
                        mocker.PropertyMock(return_value=_WID),
                        create=True)
    return resource


def _make_client(mocker, resource, get_response=None, post_response=None):
    mock_client = mocker.MagicMock()
    if get_response is not None:
        mock_client.get.return_value.json.return_value = get_response
    if post_response is not None:
        mock_client.post.return_value.json.return_value = post_response
    mocker.patch.object(resource, "client", mock_client, create=True)
    return mock_client


@pytest.mark.unit
class TestAwsCredentials:
    def test_registration(self):
        assert DuploAwsCredentials.kind == "aws_credentials"
        assert DuploAwsCredentials.scope == "workspace"
        assert DuploAwsCredentials._client_name == "helpdesk"

    def test_no_mutating_commands(self):
        from duplocloud.commander import commands_for
        cmds = commands_for("aws_credentials")
        for verb in ("create", "update", "delete", "apply"):
            assert verb not in cmds

    def test_list_filters_aws_scopes(self, mocker):
        resource = _make_resource(mocker)
        scopes = [{"id": "s-1", "name": "aws-prod"}]
        client = _make_client(mocker, resource,
                              get_response={"success": True, "data": scopes})
        assert resource.list() == scopes
        assert client.get.call_args[0][0] == (
            "user/data/workspaces/ws-1/scopes?providerTypes=AWS")

    def test_find_by_scope_name_posts_jit(self, mocker):
        resource = _make_resource(mocker)
        scopes = [{"id": "s-1", "name": "aws-prod"},
                  {"id": "s-2", "name": "aws-dev"}]
        client = _make_client(
            mocker, resource,
            get_response={"success": True, "data": scopes},
            post_response={"success": True, "data": _CREDS})
        creds = resource.find(name="AWS-PROD")
        assert creds["accessKeyId"] == "AKIA123"
        assert client.post.call_args[0][0] == (
            "user/data/workspaces/ws-1/scopes/s-1/aws/jitAccess")

    def test_find_defaults_to_only_scope(self, mocker):
        resource = _make_resource(mocker)
        client = _make_client(
            mocker, resource,
            get_response={"success": True,
                          "data": [{"id": "s-1", "name": "aws-prod"}]},
            post_response={"success": True, "data": _CREDS})
        resource.find()
        assert client.post.call_args[0][0].endswith("/scopes/s-1/aws/jitAccess")

    def test_find_ambiguous_without_name(self, mocker):
        resource = _make_resource(mocker)
        client = _make_client(
            mocker, resource,
            get_response={"success": True,
                          "data": [{"id": "s-1", "name": "a"},
                                   {"id": "s-2", "name": "b"}]})
        with pytest.raises(DuploError, match="Available: a, b"):
            resource.find()
        client.post.assert_not_called()

    def test_find_unknown_scope_lists_available(self, mocker):
        resource = _make_resource(mocker)
        _make_client(mocker, resource,
                     get_response={"success": True,
                                   "data": [{"id": "s-1", "name": "a"}]})
        with pytest.raises(DuploError, match="'nope' not found.*Available: a"):
            resource.find(name="nope")

    def test_find_by_resource_group_builds_env_route(self, mocker):
        resource = _make_resource(mocker)
        rg_svc = mocker.MagicMock()
        rg_svc.find.return_value = {"id": "rg-1", "name": "my-rg",
                                    "spec": {"environmentId": "env-1"}}
        resource.duplo.load.return_value = rg_svc
        client = _make_client(
            mocker, resource,
            post_response={"success": True, "data": _CREDS})
        creds = resource.find(resource_group="my-rg")
        assert creds["region"] == "us-east-2"
        assert client.post.call_args[0][0] == (
            "user/data/workspaces/ws-1/environments/env-1"
            "/resource-groups/rg-1/aws/jitAccess")
        resource.duplo.load.assert_any_call("resource_group")

    def test_resource_group_without_env_errors(self, mocker):
        resource = _make_resource(mocker)
        rg_svc = mocker.MagicMock()
        rg_svc.find.return_value = {"id": "rg-1", "name": "my-rg", "spec": {}}
        resource.duplo.load.return_value = rg_svc
        client = _make_client(mocker, resource)
        with pytest.raises(DuploError, match="no environmentId"):
            resource.find(resource_group="my-rg")
        client.post.assert_not_called()

    def test_empty_credentials_error(self, mocker):
        resource = _make_resource(mocker)
        _make_client(
            mocker, resource,
            get_response={"success": True,
                          "data": [{"id": "s-1", "name": "a"}]},
            post_response={"success": True, "data": {}})
        with pytest.raises(DuploError, match="no AWS credentials"):
            resource.find(name="a")
