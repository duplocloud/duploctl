import pytest
from typing import Any, Dict, Optional, Callable
from duplocloud.errors import DuploError

def execute_test(func: Callable, *args, **kwargs) -> Any:
    """Standardized test execution with error handling.
    
    Args:
        func: Function to execute
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        Any: Result of the function execution
        
    Raises:
        pytest.fail: If the function execution fails
    """
    try:
        return func(*args, **kwargs)
    except DuploError as e:
        pytest.fail(f"Test failed: {e}")

def assert_response(response: Dict[str, Any], 
                   expected_message: str,
                   status_code: int = 200,
                   exact_match: bool = True) -> None:
    """Standard response validation.
    
    Args:
        response: Response dictionary to validate
        expected_message: Expected message in the response
        status_code: Expected status code (default: 200)
        exact_match: Whether to check for exact message match (default: True)
    """
    assert response is not None, "Response should not be None"
    assert "message" in response, "Response should contain 'message'"
    
    if exact_match:
        assert response["message"] == expected_message
    else:
        assert expected_message in response["message"]
        
    if "status_code" in response:
        assert response["status_code"] == status_code

def get_resource_name(tenant_name: str, 
                     resource_type: str, 
                     suffix: Optional[str] = None) -> str:
    """Generate standard resource name.
    
    Args:
        tenant_name: Name of the tenant
        resource_type: Type of resource
        suffix: Optional suffix for the resource name
        
    Returns:
        str: Generated resource name
    """
    name = f"duploservices-{tenant_name}-{resource_type}"
    if suffix:
        name = f"{name}-{suffix}"
    return name

def setup_resource_fixture(duplo: Any, 
                         resource_type: str,
                         request: Any,
                         suffix: Optional[str] = None) -> tuple:
    """Standard resource fixture setup.
    
    Args:
        duplo: DuploClient instance
        resource_type: Type of resource to load
        request: pytest request object
        suffix: Optional suffix for resource name
        
    Returns:
        tuple: (resource, resource_name)
    """
    resource = duplo.load(resource_type)
    tenant_name = resource.tenant["AccountName"]
    resource_name = get_resource_name(tenant_name, resource_type, suffix)
    if request and hasattr(request, "cls"):
        request.cls.resource_name = resource_name
    return resource, resource_name