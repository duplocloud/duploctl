import pytest
from duplocloud.errors import DuploError, DuploExpiredCache, DuploFailedResource, DuploStillWaiting

@pytest.mark.unit
def test_duplo_error_defaults():
    err = DuploError("Something went wrong")
    assert isinstance(err, DuploError)
    assert str(err) == "Something went wrong"
    assert err.code == 1
    assert err.response is None

@pytest.mark.unit
def test_duplo_error_custom_code():
    err = DuploError("Custom code", code=500)
    assert err.code == 500

@pytest.mark.unit
def test_duplo_expired_cache():
    key = "test_key"
    err = DuploExpiredCache(key)
    assert isinstance(err, DuploExpiredCache)
    assert isinstance(err, DuploError)
    assert err.key == key
    assert err.code == 404
    assert str(err) == "Cache item {key} is expired"

@pytest.mark.unit
def test_duplo_failed_resource():
    err = DuploFailedResource("test-resource")
    assert isinstance(err, DuploFailedResource)
    assert err.code == 412
    assert str(err) == "test-resource is in a failed state"

@pytest.mark.unit
def test_duplo_still_waiting():
    err = DuploStillWaiting("delayed-service")
    assert isinstance(err, DuploStillWaiting)
    assert err.code == 408
    assert str(err) == "delayed-service is in a waiting state"

@pytest.mark.integration
@pytest.mark.parametrize("exception_class,init_arg,expected_str,expected_code", [
    (DuploExpiredCache, "mykey", "Cache item {key} is expired", 404),
    (DuploFailedResource, "resource-A", "resource-A is in a failed state", 412),
    (DuploStillWaiting, "resource-B", "resource-B is in a waiting state", 408),
])
def test_integration_duplo_exceptions(exception_class, init_arg, expected_str, expected_code):
    err = exception_class(init_arg)
    assert isinstance(err, DuploError)
    assert str(err) == expected_str
    assert err.code == expected_code
