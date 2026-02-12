import pytest
import time
from unittest.mock import MagicMock
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResourceV3
from duplo_resource.aws_secret import DuploAwsSecret

@pytest.fixture(scope="class")
def aws_secret_resource(duplo):
    """Fixture to load the AWS Secret resource and define the secret name."""
    resource = duplo.load("aws_secret")
    resource.duplo.wait = True
    tenant = resource.tenant["AccountName"]
    secret_name = f"duploservices-{tenant}-secret"
    return resource, secret_name

def execute_test(func, *args, **kwargs):
    """Helper function to execute a test and handle errors."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")

@pytest.fixture
def aws_secret(mocker):
    """Create a DuploAwsSecret with a mocked client for unit tests."""
    mock_client = mocker.MagicMock()
    mock_client.tenant = "mytenant"
    mock_client.wait = False
    secret = DuploAwsSecret(mock_client)
    secret._tenant = {"AccountName": "mytenant", "TenantId": "tid-123"}
    secret._tenant_id = "tid-123"
    return secret


# --- name_from_body ---

@pytest.mark.unit
def test_name_from_body(aws_secret):
    """name_from_body returns the Name key from the body."""
    assert aws_secret.name_from_body({"Name": "mysecret"}) == "mysecret"

@pytest.mark.unit
def test_name_from_body_missing(aws_secret):
    """name_from_body returns None when Name is absent."""
    assert aws_secret.name_from_body({}) is None


# --- find ---

@pytest.mark.unit
def test_find_retries_with_prefix_on_404(aws_secret):
    """Regression: find should retry with the prefixed name when the API returns 404.

    Previously find only retried on 400, so a 404 for the short name
    would raise 'Resource not found' without ever trying the full
    duploservices-<tenant>-<name> prefixed name.
    """
    secret_data = {"Name": "duploservices-mytenant-mysecret", "SecretString": "s3cret"}
    prefixed_response = MagicMock()
    prefixed_response.json.return_value = secret_data

    # First call (short name) returns 404, second call (prefixed) succeeds
    aws_secret.duplo.get.side_effect = [
        DuploError("Resource not found", 404),
        prefixed_response,
    ]

    result = aws_secret.find("mysecret", show_sensitive=True)
    assert result == secret_data
    assert aws_secret.duplo.get.call_count == 2


@pytest.mark.unit
def test_find_retries_with_prefix_on_400(aws_secret):
    """find should also retry with the prefixed name when the API returns 400."""
    secret_data = {"Name": "duploservices-mytenant-mysecret", "SecretString": "s3cret"}
    prefixed_response = MagicMock()
    prefixed_response.json.return_value = secret_data

    aws_secret.duplo.get.side_effect = [
        DuploError("Bad request", 400),
        prefixed_response,
    ]

    result = aws_secret.find("mysecret", show_sensitive=True)
    assert result == secret_data
    assert aws_secret.duplo.get.call_count == 2


@pytest.mark.unit
def test_find_raises_on_other_errors(aws_secret):
    """find should not swallow errors other than 400/404."""
    aws_secret.duplo.get.side_effect = DuploError("Server error", 500)

    with pytest.raises(DuploError) as exc_info:
        aws_secret.find("mysecret", show_sensitive=True)
    assert exc_info.value.code == 500
    assert aws_secret.duplo.get.call_count == 1


@pytest.mark.unit
def test_find_does_not_double_prefix(aws_secret):
    """find should not retry with a prefixed name when the name is already prefixed."""
    prefixed = "duploservices-mytenant-mysecret"
    aws_secret.duplo.get.side_effect = DuploError("Not found", 404)

    with pytest.raises(DuploError) as exc_info:
        aws_secret.find(prefixed, show_sensitive=True)
    assert exc_info.value.code == 404
    # Only one call — no retry with double prefix
    assert aws_secret.duplo.get.call_count == 1


@pytest.mark.unit
def test_find_obfuscates_secret_by_default(aws_secret):
    """find should mask SecretString when show_sensitive is False."""
    secret_data = {"Name": "mysecret", "SecretString": "s3cret"}
    mock_response = MagicMock()
    mock_response.json.return_value = secret_data

    aws_secret.duplo.get.return_value = mock_response

    result = aws_secret.find("mysecret", show_sensitive=False)
    assert result["SecretString"] == "******"
    assert result["Name"] == "mysecret"


# --- create ---

@pytest.mark.unit
def test_create_with_name_and_value(aws_secret, mocker):
    """create sets Name and SecretString from args and posts to the API."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": "ok"}
    aws_secret.duplo.post.return_value = mock_response

    result = aws_secret.create(name="mysecret", value="myvalue")
    assert result == {"message": "ok"}
    posted_body = aws_secret.duplo.post.call_args[0][1]
    assert posted_body["Name"] == "mysecret"
    assert posted_body["SecretString"] == "myvalue"


@pytest.mark.unit
def test_create_with_body(aws_secret, mocker):
    """create uses provided body."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": "ok"}
    aws_secret.duplo.post.return_value = mock_response

    body = {"Name": "fromsecret", "SecretString": "fromvalue"}
    result = aws_secret.create(body=body)
    assert result == {"message": "ok"}


@pytest.mark.unit
def test_create_name_overrides_body_name(aws_secret, mocker):
    """When both name and body are provided, name takes precedence."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": "ok"}
    aws_secret.duplo.post.return_value = mock_response

    body = {"Name": "old-name", "SecretString": "val"}
    aws_secret.create(name="new-name", body=body)
    posted_body = aws_secret.duplo.post.call_args[0][1]
    assert posted_body["Name"] == "new-name"


@pytest.mark.unit
def test_create_with_data(aws_secret, mocker):
    """create merges a datamap into the body's SecretString."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": "ok"}
    aws_secret.duplo.post.return_value = mock_response

    aws_secret.create(name="mysecret", data={"key1": "val1"})
    posted_body = aws_secret.duplo.post.call_args[0][1]
    assert '"key1": "val1"' in posted_body["SecretString"]


@pytest.mark.unit
def test_create_with_data_and_existing_body_secret_string(aws_secret, mocker):
    """create merges datamap into an existing SecretString from the body."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": "ok"}
    aws_secret.duplo.post.return_value = mock_response

    body = {"Name": "mysecret", "SecretString": '{"existing": "data"}'}
    aws_secret.create(name="mysecret", body=body, data={"new": "val"})
    posted_body = aws_secret.duplo.post.call_args[0][1]
    import json
    merged = json.loads(posted_body["SecretString"])
    assert merged == {"existing": "data", "new": "val"}


@pytest.mark.unit
def test_create_dryrun(aws_secret):
    """create with dryrun returns the body without posting."""
    result = aws_secret.create(name="mysecret", value="val", dryrun=True)
    assert result["Name"] == "mysecret"
    assert result["SecretString"] == "val"
    aws_secret.duplo.post.assert_not_called()


@pytest.mark.unit
def test_create_no_name_no_body_raises(aws_secret):
    """create raises when neither name nor body is provided."""
    with pytest.raises(DuploError, match="Name is required"):
        aws_secret.create()


@pytest.mark.unit
def test_create_value_and_data_raises(aws_secret):
    """create raises when both value and data are provided."""
    with pytest.raises(DuploError, match="cannot use --value"):
        aws_secret.create(name="mysecret", value="v", data={"k": "v"})


# --- update ---

@pytest.mark.unit
def test_update_with_name_and_value(aws_secret, mocker):
    """update sets SecretString from value and puts to the API."""
    mocker.patch.object(aws_secret, "find", return_value={"Name": "mysecret", "SecretString": "old"})
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": "updated"}
    aws_secret.duplo.put.return_value = mock_response

    result = aws_secret.update(name="mysecret", value="newval")
    assert result == {"message": "updated"}
    put_body = aws_secret.duplo.put.call_args[0][1]
    assert put_body["SecretString"] == "newval"
    assert put_body["SecretValueType"] == "plain"


@pytest.mark.unit
def test_update_with_data_merges(aws_secret, mocker):
    """update merges datamap into the current secret's SecretString."""
    mocker.patch.object(aws_secret, "find", return_value={
        "Name": "mysecret", "SecretString": '{"existing": "data"}'
    })
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": "updated"}
    aws_secret.duplo.put.return_value = mock_response

    result = aws_secret.update(name="mysecret", data={"new": "val"})
    assert result == {"message": "updated"}
    import json
    put_body = aws_secret.duplo.put.call_args[0][1]
    merged = json.loads(put_body["SecretString"])
    assert merged == {"existing": "data", "new": "val"}


@pytest.mark.unit
def test_update_dryrun(aws_secret, mocker):
    """update with dryrun returns the body without putting."""
    mocker.patch.object(aws_secret, "find", return_value={"Name": "mysecret", "SecretString": "old"})

    result = aws_secret.update(name="mysecret", value="newval", dryrun=True)
    assert result["SecretString"] == "newval"
    assert result["SecretValueType"] == "plain"
    aws_secret.duplo.put.assert_not_called()


@pytest.mark.unit
def test_update_name_from_body(aws_secret, mocker):
    """update extracts name from body when name arg is not provided."""
    mocker.patch.object(aws_secret, "find", return_value={"Name": "bodyname", "SecretString": "old"})
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": "updated"}
    aws_secret.duplo.put.return_value = mock_response

    result = aws_secret.update(body={"Name": "bodyname"}, value="v")
    assert result == {"message": "updated"}
    aws_secret.find.assert_called_once_with("bodyname", True)


@pytest.mark.unit
def test_update_no_name_no_body_raises(aws_secret):
    """update raises when neither name nor body is provided."""
    with pytest.raises(DuploError, match="Name is required"):
        aws_secret.update()


@pytest.mark.unit
def test_update_value_and_data_raises(aws_secret):
    """update raises when both value and data are provided."""
    with pytest.raises(DuploError, match="cannot pass both"):
        aws_secret.update(name="s", value="v", data={"k": "v"})


@pytest.mark.unit
def test_update_body_without_name_raises(aws_secret):
    """update raises when body has no Name and name arg is not given."""
    with pytest.raises(DuploError, match="Name is required when the body does not have a name"):
        aws_secret.update(body={"SomeOther": "field"})


# --- delete ---

@pytest.mark.unit
def test_delete_success(aws_secret, mocker):
    """delete calls parent delete and returns a success message."""
    mocker.patch.object(DuploResourceV3, "delete", return_value={"message": "ok"})

    result = aws_secret.delete("mysecret")
    assert result["message"] == "Successfully deleted secret 'mysecret'"
    DuploResourceV3.delete.assert_called_once_with("mysecret")


@pytest.mark.unit
def test_delete_retries_with_prefix_on_404(aws_secret, mocker):
    """delete retries with the prefixed name when parent returns 404."""
    mocker.patch.object(
        DuploResourceV3, "delete",
        side_effect=[DuploError("Not found", 404), {"message": "ok"}]
    )

    result = aws_secret.delete("mysecret")
    assert result["message"] == "Successfully deleted secret 'mysecret'"
    assert DuploResourceV3.delete.call_count == 2
    DuploResourceV3.delete.assert_called_with("duploservices-mytenant-mysecret")


@pytest.mark.unit
def test_delete_does_not_double_prefix(aws_secret, mocker):
    """delete should not retry with a prefixed name when the name is already prefixed."""
    prefixed = "duploservices-mytenant-mysecret"
    mocker.patch.object(DuploResourceV3, "delete", side_effect=DuploError("Not found", 404))

    with pytest.raises(DuploError) as exc_info:
        aws_secret.delete(prefixed)
    assert exc_info.value.code == 404
    assert DuploResourceV3.delete.call_count == 1


@pytest.mark.unit
def test_delete_raises_on_other_errors(aws_secret, mocker):
    """delete propagates non-404 errors."""
    mocker.patch.object(DuploResourceV3, "delete", side_effect=DuploError("Server error", 500))

    with pytest.raises(DuploError) as exc_info:
        aws_secret.delete("mysecret")
    assert exc_info.value.code == 500


# --- _merge_data ---

@pytest.mark.unit
def test_merge_data_success(aws_secret):
    """_merge_data merges new keys into valid JSON SecretString."""
    import json
    result = aws_secret._merge_data('{"a": "1"}', {"b": "2"})
    assert json.loads(result) == {"a": "1", "b": "2"}


@pytest.mark.unit
def test_merge_data_invalid_json_raises(aws_secret):
    """_merge_data raises on invalid JSON."""
    with pytest.raises(DuploError, match="Unable to parse"):
        aws_secret._merge_data("not-json", {"k": "v"})


@pytest.mark.unit
def test_merge_data_non_string_values_raises(aws_secret):
    """_merge_data raises when existing JSON has non-string values."""
    with pytest.raises(DuploError, match="All values.*must be strings"):
        aws_secret._merge_data('{"a": 123}', {"b": "2"})


# --- prefixed_name ---

@pytest.mark.unit
def test_prefixed_name_regular(aws_secret):
    """prefixed_name adds a dash separator for regular names."""
    assert aws_secret.prefixed_name("mysecret") == "duploservices-mytenant-mysecret"

@pytest.mark.unit
def test_prefixed_name_slash(aws_secret):
    """prefixed_name omits the dash when name starts with a slash."""
    assert aws_secret.prefixed_name("/mysecret") == "duploservices-mytenant/mysecret"

@pytest.mark.unit
def test_prefixed_name_already_prefixed(aws_secret):
    """prefixed_name returns the name unchanged when already prefixed."""
    assert aws_secret.prefixed_name("duploservices-mytenant-secret") == "duploservices-mytenant-secret"

@pytest.mark.unit
def test_prefixed_name_unprefixed(aws_secret):
    """prefixed_name adds prefix to short names."""
    assert aws_secret.prefixed_name("secret") != "secret"


class TestAwsSecret:

    @pytest.mark.integration
    @pytest.mark.dependency(name="create_secret", scope="session")
    @pytest.mark.order(1)
    def test_create_secret(self, aws_secret_resource):
        """Test creating an AWS secret."""
        r, secret_name = aws_secret_resource
        body = {"Name": secret_name, "SecretString": '{"foo": "bar"}'}
        execute_test(r.create, name=secret_name, body=body)
        time.sleep(10)

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_secret"], scope="session")
    @pytest.mark.order(2)
    def test_find_secret(self, aws_secret_resource):
        """Test finding the created AWS secret."""
        r, secret_name = aws_secret_resource
        secret = execute_test(r.find, secret_name, show_sensitive=True)
        assert secret["Name"] == secret_name
        assert secret["SecretString"] == '{"foo": "bar"}'

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_secret"], scope="session")
    @pytest.mark.order(3)
    def test_update_secret(self, aws_secret_resource):
        """Test updating an AWS secret and verifying the update."""
        r, secret_name = aws_secret_resource
        new_value = '{"foo": "baz"}'
        execute_test(r.update, name=secret_name, value=new_value)
        # Verify the updated value
        updated_secret = execute_test(r.find, secret_name, show_sensitive=True)
        assert "SecretString" in updated_secret, "SecretString key missing in response"
        assert updated_secret["SecretString"] == new_value

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_secret"], scope="session")
    @pytest.mark.order(4)
    def test_delete_secret(self, aws_secret_resource):
        """Test deleting an AWS secret."""
        r, secret_name = aws_secret_resource
        response = execute_test(r.delete, secret_name)
        assert response.get("message") == f"Successfully deleted secret '{secret_name}'"
