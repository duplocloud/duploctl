import pytest
from unittest.mock import MagicMock
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResourceV3
from duplo_resource.ingress import DuploIngress
from .conftest import get_test_data


@pytest.fixture
def ingress(mocker):
    """Create a DuploIngress with a mocked client for unit tests."""
    mock_client = mocker.MagicMock()
    mock_client.tenant = "mytenant"
    mock_client.wait = False
    resource = DuploIngress(mock_client)
    resource._tenant = {"AccountName": "mytenant", "TenantId": "tid-123"}
    resource._tenant_id = "tid-123"
    return resource


@pytest.fixture
def ingress_body():
    """Sample ingress body matching the test data format."""
    return {
        "name": "duploctl",
        "ingressClassName": "alb",
        "lbConfig": {
            "listeners": {"https": [443], "http": [80]},
            "dnsPrefix": "duploctl",
            "isPublic": True,
        },
        "rules": [
            {
                "path": "/",
                "pathType": "Prefix",
                "serviceName": "nginx",
                "port": 80,
            }
        ],
    }


# --- endpoint ---

@pytest.mark.unit
def test_endpoint_list(ingress):
    """endpoint() with no args returns the tenant-scoped list path."""
    assert ingress.endpoint() == "v3/subscriptions/tid-123/k8s/ingress"


@pytest.mark.unit
def test_endpoint_find(ingress):
    """endpoint(name) returns the tenant-scoped resource path."""
    assert ingress.endpoint("myingress") == "v3/subscriptions/tid-123/k8s/ingress/myingress"


@pytest.mark.unit
def test_scope_is_tenant(ingress):
    """Ingress should be tenant-scoped."""
    assert ingress.scope == "tenant"


@pytest.mark.unit
def test_api_version(ingress):
    """Ingress should use v3 API."""
    assert ingress.api_version == "v3"


@pytest.mark.unit
def test_slug(ingress):
    """Ingress slug should be k8s/ingress."""
    assert ingress.slug == "k8s/ingress"


# --- name_from_body ---

@pytest.mark.unit
def test_name_from_body(ingress, ingress_body):
    """name_from_body extracts the top-level name field."""
    assert ingress.name_from_body(ingress_body) == "duploctl"


# --- list ---

@pytest.mark.unit
def test_list(ingress):
    """list returns the parsed JSON response."""
    mock_response = MagicMock()
    mock_response.json.return_value = [{"name": "ing1"}, {"name": "ing2"}]
    ingress.duplo.get.return_value = mock_response

    result = ingress.list()
    assert len(result) == 2
    ingress.duplo.get.assert_called_once_with("v3/subscriptions/tid-123/k8s/ingress")


# --- create ---

@pytest.mark.unit
def test_create(ingress, ingress_body):
    """create posts the body and returns a success message."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"name": "duploctl"}
    ingress.duplo.post.return_value = mock_response

    result = ingress.create(body=ingress_body)
    assert result["message"] == "Successfully Created an Ingress 'duploctl'"
    ingress.duplo.post.assert_called_once_with(
        "v3/subscriptions/tid-123/k8s/ingress", ingress_body
    )


# --- find ---

@pytest.mark.unit
def test_find(ingress):
    """find calls the correct endpoint with the name."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"name": "myingress"}
    ingress.duplo.get.return_value = mock_response

    result = ingress.find("myingress")
    assert result["name"] == "myingress"
    ingress.duplo.get.assert_called_once_with(
        "v3/subscriptions/tid-123/k8s/ingress/myingress"
    )


# --- delete ---

@pytest.mark.unit
def test_delete(ingress):
    """delete calls the correct endpoint and returns a success message."""
    ingress.duplo.delete.return_value = MagicMock()
    result = ingress.delete("myingress")
    assert result["message"] == "k8s/ingress/myingress deleted"
    ingress.duplo.delete.assert_called_once_with(
        "v3/subscriptions/tid-123/k8s/ingress/myingress"
    )


# --- update ---

@pytest.mark.unit
def test_update(ingress, ingress_body, mocker):
    """update finds the resource, then puts the body."""
    mocker.patch.object(ingress, "find", return_value=ingress_body)
    mock_response = MagicMock()
    mock_response.json.return_value = ingress_body
    ingress.duplo.put.return_value = mock_response

    result = ingress.update(name="duploctl", body=ingress_body)
    assert result["message"] == "Successfully Updated an Ingress 'duploctl'"


@pytest.mark.unit
def test_update_name_body_mismatch_raises(ingress, ingress_body):
    """update raises when name and body name don't match."""
    with pytest.raises(DuploError, match="must match"):
        ingress.update(name="other", body=ingress_body)


# --- Integration tests ---

@pytest.fixture(scope="class")
def ingress_resource(duplo, request):
    """Fixture to load an Ingress resource."""
    resource = duplo.load("ingress")
    request.cls.ingress_name = None
    return resource

def execute_test(func, *args, **kwargs):
    """Helper function to execute a test and handle errors."""
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")

class TestIngress:

    @pytest.mark.integration
    @pytest.mark.dependency(name="create_ingress", scope="session")
    @pytest.mark.order(6)
    def test_create_ingress(self, ingress_resource, request):
        """Test creating an Ingress resource."""
        r = ingress_resource
        body = get_test_data("ingress")
        response = execute_test(r.create, body=body)
        assert response.get("message") and f"Successfully Created an Ingress '{body['name']}'" in response["message"], "Ingress creation failed"
        request.cls.ingress_name = body['name']

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_ingress"], scope="session")
    @pytest.mark.order(7)
    def test_update_ingress(self, ingress_resource):
        """Test updating an Ingress resource."""
        r = ingress_resource
        update_body = get_test_data("ingress")
        response = execute_test(r.update, name=self.ingress_name, body=update_body)
        assert response.get("message") and f"Successfully Updated an Ingress '{update_body['name']}'" in response["message"], "Ingress updation failed"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_ingress"], scope="session")
    @pytest.mark.order(8)
    def test_list_ingress(self, ingress_resource):
        """Test listing an Ingress."""
        r = ingress_resource
        ingresses = execute_test(r.list)
        assert isinstance(ingresses, list), "Ingress list response is not a list"
        assert len(ingresses) > 0, "No Ingress found"

    @pytest.mark.integration
    @pytest.mark.dependency(depends=["create_ingress"], scope="session")
    @pytest.mark.order(997)
    def test_delete_ingress(self, ingress_resource):
        """Test deleting an Ingress."""
        r = ingress_resource
        assert self.ingress_name is not None, "Ingress name not found!"
        response = execute_test(r.delete, name=self.ingress_name)
        assert response.get("message") == f"k8s/ingress/{self.ingress_name} deleted"
