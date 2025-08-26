import pytest
from duplocloud.errors import DuploError
from .conftest import get_test_data

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
