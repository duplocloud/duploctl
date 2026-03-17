import pytest
from duplocloud.errors import DuploError, DuploNotFound
from duplo_resource.infrastructure import DuploInfrastructure


def _make_infra(mocker):
    """Create a DuploInfrastructure instance with a mocked duplo client."""
    mock_duplo = mocker.MagicMock()
    mock_duplo.wait = False
    mock_duplo.validate = False
    return DuploInfrastructure(mock_duplo)


# ---------------------------------------------------------------------------
# DuploNotFound
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_duplo_not_found_message_and_code():
    """DuploNotFound carries the resource name and 404 code."""
    err = DuploNotFound("my-infra")
    assert err.code == 404
    assert "my-infra" in str(err)


@pytest.mark.unit
def test_duplo_not_found_with_kind():
    """DuploNotFound includes the kind label when provided."""
    err = DuploNotFound("my-infra", kind="Infrastructure")
    assert err.code == 404
    assert "Infrastructure" in str(err)
    assert "my-infra" in str(err)


@pytest.mark.unit
def test_duplo_not_found_is_duplo_error():
    """DuploNotFound is a subclass of DuploError."""
    err = DuploNotFound("x")
    assert isinstance(err, DuploError)


# ---------------------------------------------------------------------------
# update — happy path (no-op)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_update_returns_noop_message_when_body_matches(mocker):
    """update returns a no-op message when body fields match the existing infra."""
    infra = _make_infra(mocker)
    existing = {"Name": "my-infra", "Region": "us-west-2", "Cloud": 0}
    mocker.patch.object(infra, "find", return_value=existing)

    result = infra.update("my-infra", {"Name": "my-infra", "Region": "us-west-2"})

    assert "already exists" in result["message"]
    assert "my-infra" in result["message"]


@pytest.mark.unit
def test_update_no_body_returns_noop_message(mocker):
    """update with no body skips validation and returns a no-op message."""
    infra = _make_infra(mocker)
    mocker.patch.object(infra, "find", return_value={"Name": "my-infra"})

    result = infra.update("my-infra")

    assert "already exists" in result["message"]


@pytest.mark.unit
def test_update_logs_immutability_warning(mocker):
    """update emits a warning that infrastructure fields are immutable."""
    infra = _make_infra(mocker)
    mocker.patch.object(infra, "find", return_value={"Name": "my-infra"})

    infra.update("my-infra")

    infra.duplo.logger.warning.assert_called_once()
    assert "immutable" in infra.duplo.logger.warning.call_args[0][0]


# ---------------------------------------------------------------------------
# update — immutability enforcement
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_update_raises_when_field_differs(mocker):
    """update raises DuploError 422 when a body field differs from existing."""
    infra = _make_infra(mocker)
    existing = {"Name": "my-infra", "Region": "us-west-2", "Cloud": 0}
    mocker.patch.object(infra, "find", return_value=existing)

    with pytest.raises(DuploError) as exc_info:
        infra.update("my-infra", {"Name": "my-infra", "Region": "us-east-1"})

    assert exc_info.value.code == 422
    assert "Region" in str(exc_info.value)
    assert "immutable" in str(exc_info.value)


@pytest.mark.unit
def test_update_error_lists_all_changed_fields(mocker):
    """update error message includes every changed field name."""
    infra = _make_infra(mocker)
    existing = {
        "Name": "my-infra",
        "Region": "us-west-2",
        "Cloud": 0,
        "EnableK8Cluster": False,
    }
    mocker.patch.object(infra, "find", return_value=existing)

    with pytest.raises(DuploError) as exc_info:
        infra.update("my-infra", {
            "Name": "my-infra",
            "Region": "us-east-1",
            "EnableK8Cluster": True,
        })

    msg = str(exc_info.value)
    assert "Region" in msg
    assert "EnableK8Cluster" in msg


@pytest.mark.unit
def test_update_ignores_keys_not_in_existing(mocker):
    """update does not raise for body keys absent from the existing infra."""
    infra = _make_infra(mocker)
    mocker.patch.object(infra, "find", return_value={"Name": "my-infra"})

    # "NewKey" is not in existing — should not be treated as a diff
    result = infra.update("my-infra", {"Name": "my-infra", "NewKey": "value"})

    assert "already exists" in result["message"]


# ---------------------------------------------------------------------------
# update — not found propagates DuploNotFound for apply() to catch
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_update_propagates_duplo_not_found(mocker):
    """update lets DuploNotFound from find() bubble up for apply() to catch."""
    infra = _make_infra(mocker)
    mocker.patch.object(infra, "find", side_effect=DuploNotFound("missing-infra"))

    with pytest.raises(DuploNotFound):
        infra.update("missing-infra", {"Name": "missing-infra"})


@pytest.mark.unit
def test_update_propagates_auth_errors(mocker):
    """update does not swallow non-404 errors (e.g. auth failures)."""
    infra = _make_infra(mocker)
    mocker.patch.object(infra, "find", side_effect=DuploError("Unauthorized", 401))

    with pytest.raises(DuploError) as exc_info:
        infra.update("my-infra")

    assert exc_info.value.code == 401
