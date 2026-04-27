import pytest

from duplo_resource.ssm_param import DuploParam


def _make_ssm(mocker):
    """Create a DuploParam instance with a mocked duplo client."""
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = False
    mock_duplo.validate = False
    ssm = DuploParam(mock_duplo)
    ssm._tenant = {"AccountName": "myaccount", "TenantId": "tid-123"}
    ssm._tenant_id = "tid-123"
    return ssm


def _mock_client(mocker, ssm, json_payload):
    """Swap ssm.client for a mock returning json_payload on get/put/delete."""
    mock_client = mocker.MagicMock()
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = json_payload
    mock_client.get.return_value = mock_response
    mock_client.put.return_value = mock_response
    mock_client.delete.return_value = mock_response
    mocker.patch.object(ssm, "client", mock_client)
    return mock_client


# --- _encoded_name ---

@pytest.mark.unit
def test_encoded_name_double_encodes_slashes(mocker):
    """Hierarchical names must reach the API double-encoded."""
    ssm = _make_ssm(mocker)
    assert (
        ssm._encoded_name("/customer/web/demo")
        == "%252Fcustomer%252Fweb%252Fdemo"
    )


@pytest.mark.unit
def test_encoded_name_flat_name_still_double_encoded(mocker):
    """A flat name with no slashes remains safe (no change beyond idempotent encoding)."""
    ssm = _make_ssm(mocker)
    assert ssm._encoded_name("myparam") == "myparam"


# --- find ---

@pytest.mark.unit
def test_find_uses_encoded_name_in_url(mocker):
    """find GETs the double-encoded path segment, not the raw name."""
    ssm = _make_ssm(mocker)
    mock_client = _mock_client(
        mocker, ssm, {"Name": "/customer/web/demo", "Type": "String", "Value": "v"}
    )

    ssm.find("/customer/web/demo")

    url = mock_client.get.call_args[0][0]
    assert url == (
        "v3/subscriptions/tid-123/aws/ssmParameter/"
        "%252Fcustomer%252Fweb%252Fdemo"
    )


@pytest.mark.unit
def test_find_obfuscates_secure_string_by_default(mocker):
    """SecureString values are masked when show_sensitive=False."""
    ssm = _make_ssm(mocker)
    _mock_client(
        mocker, ssm, {"Name": "secret", "Type": "SecureString", "Value": "hunter2"}
    )

    result = ssm.find("secret")
    assert result["Value"] == "*******"


# --- update ---

@pytest.mark.unit
def test_update_puts_to_encoded_url(mocker):
    """update PUTs to the double-encoded path segment."""
    ssm = _make_ssm(mocker)
    mock_client = _mock_client(
        mocker, ssm, {"Name": "/customer/web/demo", "Type": "String", "Value": "old"}
    )

    ssm.update(name="/customer/web/demo", value="new")

    put_url = mock_client.put.call_args[0][0]
    put_body = mock_client.put.call_args[0][1]
    assert put_url == (
        "v3/subscriptions/tid-123/aws/ssmParameter/"
        "%252Fcustomer%252Fweb%252Fdemo"
    )
    assert put_body["Value"] == "new"
    assert put_body["Name"] == "/customer/web/demo"


@pytest.mark.unit
def test_update_string_list_merge(mocker):
    """Merge strategy on StringList appends the new value."""
    ssm = _make_ssm(mocker)
    mock_client = _mock_client(
        mocker, ssm, {"Name": "list", "Type": "StringList", "Value": "a,b"}
    )

    ssm.update(name="list", value="c")

    put_body = mock_client.put.call_args[0][1]
    assert put_body["Value"] == "a,b,c"


@pytest.mark.unit
def test_update_with_body_skips_fetch_and_puts_directly(mocker):
    """Body-style update PUTs the given body without calling find()."""
    ssm = _make_ssm(mocker)
    mock_client = _mock_client(mocker, ssm, {})

    supplied = {"Name": "/a/b", "Type": "String", "Value": "v"}
    ssm.update(name="/a/b", body=supplied)

    mock_client.get.assert_not_called()
    put_url = mock_client.put.call_args[0][0]
    put_body = mock_client.put.call_args[0][1]
    assert put_url.endswith("/%252Fa%252Fb")
    assert put_body is supplied


@pytest.mark.unit
def test_update_securestring_with_patches_preserves_real_value(mocker):
    """Patch-style update on a SecureString must PUT the real value, not the
    obfuscated '****' that find() returns by default. Regression test for the
    data-loss path flagged in PR #257 review."""
    ssm = _make_ssm(mocker)
    mock_client = _mock_client(
        mocker,
        ssm,
        {
            "Name": "mysecret",
            "Type": "SecureString",
            "Value": "realsecret",
            "Description": "old",
        },
    )
    ssm.duplo.jsonpatch.side_effect = (
        lambda data, patches: {**data, "Description": patches[0]["value"]}
    )

    ssm.update(
        name="mysecret",
        patches=[{"op": "replace", "path": "/Description", "value": "new desc"}],
    )

    put_body = mock_client.put.call_args[0][1]
    assert put_body["Value"] == "realsecret"
    assert put_body["Description"] == "new desc"
    assert "*" not in put_body["Value"]


# --- apply (V3 base flow) ---

@pytest.mark.unit
def test_apply_update_path_uses_encoded_url(mocker):
    """apply -> update (existing param) PUTs to the encoded URL with the body."""
    ssm = _make_ssm(mocker)
    mock_client = _mock_client(
        mocker, ssm, {"Name": "/customer/web/demo", "Type": "String", "Value": "old"}
    )

    body = {"Name": "/customer/web/demo", "Type": "String", "Value": "new"}
    ssm.apply(body=body)

    put_url = mock_client.put.call_args[0][0]
    put_body = mock_client.put.call_args[0][1]
    assert put_url.endswith("/%252Fcustomer%252Fweb%252Fdemo")
    assert put_body["Value"] == "new"


# --- delete ---

@pytest.mark.unit
def test_delete_uses_encoded_url_and_returns_raw_name(mocker):
    """delete hits the encoded URL but reports the original name in the message."""
    ssm = _make_ssm(mocker)
    mock_client = _mock_client(mocker, ssm, {})

    result = ssm.delete("/customer/web/demo")

    delete_url = mock_client.delete.call_args[0][0]
    assert delete_url == (
        "v3/subscriptions/tid-123/aws/ssmParameter/"
        "%252Fcustomer%252Fweb%252Fdemo"
    )
    assert result["message"] == "aws/ssmParameter//customer/web/demo deleted"
