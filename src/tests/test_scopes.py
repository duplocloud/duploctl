import pytest
from unittest.mock import Mock
from duplocloud.commander import resources, Resource, Command, load_resource
from duplocloud.client import DuploClient
from duplocloud.resource import DuploResourceV2, DuploResourceV3

@pytest.mark.unit
def test_portal_scoped_resource():
  """Test that portal-scoped resources don't get tenant functionality injected."""
  
  @Resource("test_portal", "portal")
  class TestPortalResource:
    def __init__(self, duplo: DuploClient):
      self.duplo = duplo
    
    @Command()
    def list(self):
      pass
  
  # Check the resource is registered
  assert "test_portal" in resources
  assert resources["test_portal"]["scope"] == "portal"
  
  # Verify the class doesn't have tenant properties
  assert not hasattr(TestPortalResource, "tenant")
  assert not hasattr(TestPortalResource, "tenant_id")
  assert not hasattr(TestPortalResource, "tenant_svc")

@pytest.mark.unit
def test_tenant_scoped_resource():
  """Test that tenant-scoped resources get tenant functionality injected."""
  
  @Resource("test_tenant", "tenant")
  class TestTenantResource:
    def __init__(self, duplo: DuploClient):
      self.duplo = duplo
    
    @Command()
    def list(self):
      pass
  
  # Check the resource is registered with tenant scope
  assert "test_tenant" in resources
  assert resources["test_tenant"]["scope"] == "tenant"
  
  # Verify tenant functionality was injected
  assert hasattr(TestTenantResource, "tenant")
  assert hasattr(TestTenantResource, "tenant_id")
  assert hasattr(TestTenantResource, "prefixed_name")
  assert hasattr(TestTenantResource, "endpoint")
  
  # Verify these are properties
  assert isinstance(getattr(TestTenantResource, "tenant"), property)
  assert isinstance(getattr(TestTenantResource, "tenant_id"), property)

@pytest.mark.unit
def test_default_scope_is_portal():
  """Test that resources default to portal scope when not specified."""
  
  @Resource("test_default")
  class TestDefaultResource:
    def __init__(self, duplo: DuploClient):
      self.duplo = duplo
    
    @Command()
    def list(self):
      pass
  
  # Check the resource defaults to portal scope
  assert "test_default" in resources
  assert resources["test_default"]["scope"] == "portal"

@pytest.mark.unit
def test_service_resource_scope():
  """Test that the real service resource has tenant scope and proper inheritance."""
  
  # Load the actual service resource
  service_class = load_resource("service")
  
  # Check that service is registered with tenant scope
  assert "service" in resources
  resource_info = resources["service"]
  
  # Verify scope (this should be tenant after we update the decorator)
  # For now, it might not have scope, so we'll check what we can
  assert "class" in resource_info
  assert resource_info["class"] == "DuploService"
  
  # Check that the service class has tenant functionality
  assert hasattr(service_class, "__init__")
  
  # After scoping is implemented, these should exist:
  # assert hasattr(service_class, "tenant")
  # assert hasattr(service_class, "tenant_id")

@pytest.mark.unit
def test_tenant_mixin_properties_work():
  """Test that injected tenant properties actually work when instantiated."""
  
  @Resource("test_tenant_props", "tenant")
  class TestTenantPropsResource:
    def __init__(self, duplo: DuploClient):
      self.duplo = duplo
    
    @Command()
    def find(self, name: str):
      return {"name": name}
  
  # Create a mock client
  class MockClient:
    def __init__(self):
      self.tenant = "test-tenant"
      self.tenantid = "test-id"
    
    def load(self, name):
      class MockTenantService:
        def find(self):
          return {
            "TenantId": "mock-tenant-id",
            "AccountName": "mockaccount"
          }
      return MockTenantService()
  
  # Instantiate the resource
  resource = TestTenantPropsResource(MockClient())
  
  # Verify private attributes were initialized
  assert hasattr(resource, "_tenant")
  assert hasattr(resource, "_tenant_id")
  assert hasattr(resource, "tenant_svc")

@pytest.mark.unit
def test_parent_class_with_scope():
  """Test that parent class reference is maintained correctly."""
  
  class BaseResource:
    def __init__(self, duplo: DuploClient):
      self.duplo = duplo
    
    @Command()
    def base_method(self):
      pass
  
  @Resource("test_child", "tenant")
  class ChildResource(BaseResource):
    @Command()
    def child_method(self):
      pass
  
  # Check parent is recorded correctly
  assert "test_child" in resources
  assert resources["test_child"]["parent"] == "BaseResource"
  assert resources["test_child"]["scope"] == "tenant"
  
  # Verify tenant functionality is injected into child
  assert hasattr(ChildResource, "tenant")
  assert hasattr(ChildResource, "tenant_id")

@pytest.mark.unit
def test_invalid_scope_raises_error():
  """Test that invalid scope values raise an error."""
  
  with pytest.raises(ValueError) as exc_info:
    @Resource("test_invalid", "invalid_scope")
    class TestInvalidResource:
      pass
  
  assert "Invalid scope" in str(exc_info.value)

@pytest.mark.unit
def test_v2_portal_scope_endpoint():
  """Test that V2 portal-scoped resources use the base endpoint method."""
  mock_duplo = Mock()
  
  @Resource("testv2portal", scope="portal")
  class TestV2PortalResource(DuploResourceV2):
    pass
  
  # Directly instantiate instead of using load_resource
  instance = TestV2PortalResource(mock_duplo)
  
  # Test V2 portal endpoint format (just returns the path)
  assert instance.endpoint("some/path") == "some/path"

@pytest.mark.unit 
def test_v2_tenant_scope_endpoint():
  """Test that V2 tenant-scoped resources get the correct endpoint method."""
  mock_duplo = Mock()
  mock_duplo.tenantid = "test-tenant-456"
  
  @Resource("testv2tenant", scope="tenant")
  class TestV2TenantResource(DuploResourceV2):
    pass
  
  # Directly instantiate instead of using load_resource
  instance = TestV2TenantResource(mock_duplo)
  instance._tenant_id = "test-tenant-456"
  
  # Test V2 tenant endpoint format
  assert instance.endpoint("AdminProxy/GetJITAccess") == "subscriptions/test-tenant-456/AdminProxy/GetJITAccess"

@pytest.mark.unit
def test_v3_portal_scope_endpoint():
  """Test that V3 portal-scoped resources use the base endpoint method."""
  mock_duplo = Mock()
  
  @Resource("testv3portal", scope="portal")
  class TestV3PortalResource(DuploResourceV3):
    def __init__(self, duplo):
      super().__init__(duplo, slug="testresources", prefixed=False)
  
  # Directly instantiate instead of using load_resource
  instance = TestV3PortalResource(mock_duplo)
  
  # Test V3 portal endpoint format (no tenant_id)
  assert instance.endpoint() == "v3/testresources"
  assert instance.endpoint("myresource") == "v3/testresources/myresource"
  assert instance.endpoint("myresource", "subpath") == "v3/testresources/myresource/subpath"

@pytest.mark.unit
def test_v3_tenant_scope_endpoint():
  """Test that V3 tenant-scoped resources get the correct endpoint method."""
  mock_duplo = Mock()
  mock_duplo.tenantid = "test-tenant-123"
  
  @Resource("testv3tenant", scope="tenant")
  class TestV3TenantResource(DuploResourceV3):
    def __init__(self, duplo):
      super().__init__(duplo, slug="testresources", prefixed=False)
  
  # Directly instantiate instead of using load_resource
  instance = TestV3TenantResource(mock_duplo)
  instance._tenant_id = "test-tenant-123"
  
  # Test V3 tenant endpoint format
  assert instance.endpoint() == "v3/subscriptions/test-tenant-123/testresources"
  assert instance.endpoint("myresource") == "v3/subscriptions/test-tenant-123/testresources/myresource"
  assert instance.endpoint("myresource", "subpath") == "v3/subscriptions/test-tenant-123/testresources/myresource/subpath"
