---
description: 'Python coding conventions and guidelines for duploctl'
applyTo: '**/*.py'
---

# Python Coding Conventions

## Python Instructions

- Write clear and concise comments for each function using Google Pydoc style.
- Ensure functions have descriptive names and include type hints.
- Provide docstrings following PEP 257 conventions.
- Use the `typing` module for type annotations (e.g., `List[str]`, `Dict[str, int]`).
- Break down complex functions into smaller, more manageable functions.
- **Always place imports at the top of the file** - never import inside functions or code blocks.

## General Instructions

- Always prioritize readability and clarity.
- For algorithm-related code, include explanations of the approach used.
- Write code with good maintainability practices, including comments on why certain design decisions were made.
- Handle edge cases and write clear exception handling.
- For libraries or external dependencies, mention their usage and purpose in comments.
- Use consistent naming conventions and follow language-specific best practices.
- Write concise, efficient, and idiomatic code that is also easily understandable.

## Code Style and Formatting

- Follow the **PEP 8** style guide for Python.
- Maintain proper indentation (use 4 spaces for each level of indentation).
- Ensure lines do not exceed 79 characters.
- Place function and class docstrings immediately after the `def` or `class` keyword.
- Use blank lines to separate functions, classes, and code blocks where appropriate.
- **Imports always go on top of the file**, never just randomly in a function or code block.

## Import Organization

Follow this order for imports:

```python
# 1. Standard library imports
import os
import sys
from pathlib import Path

# 2. Third-party imports
import requests
import yaml
from typing import List, Dict

# 3. Local application imports
from duplocloud.client import DuploClient
from duplocloud.resource import DuploResourceV2
from duplocloud.commander import Command, Resource
import duplocloud.args as args
```

## Edge Cases and Testing

- Always include test cases for critical paths of the application.
- Account for common edge cases like empty inputs, invalid data types, and large datasets.
- Include comments for edge cases and the expected behavior in those cases.
- Write unit tests for functions and document them with docstrings explaining the test cases.
- Use pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`

## Proper Documentation

- Use Google style doc guidelines for docstrings
- Do not include types in docstring (function signature already has them)
- Include the title on the first line of the docstring after the `"""`
- One empty line between the title and the description
- Make examples in the docstring if it is intended to be used a lot in different ways

```python
def calculate_area(radius: float) -> float:
    """Calculate the area of a circle given the radius.
    
    This function uses the mathematical formula π * r^2 to compute
    the area of a circle.
    
    Args:
      radius: The radius of the circle.
    
    Returns:
      The area of the circle, calculated as π * radius^2.
    
    Raises:
      ValueError: If radius is negative.
    """
    import math
    if radius < 0:
        raise ValueError("Radius cannot be negative")
    return math.pi * radius ** 2
```

## DuploCloud Resource Pattern

When creating resources for duploctl, follow this pattern:

```python
from duplocloud.client import DuploClient
from duplocloud.resource import DuploResourceV3  # or V2, or no base class
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("myresource", scope="tenant")  # scope="portal" or "tenant"
class DuploMyResource(DuploResourceV3):  # Only extend if CRUD is needed
    """Brief description of the resource.
    
    Longer description explaining what this resource manages
    and how it's used.
    """
    
    def __init__(self, duplo: DuploClient):
        super().__init__(duplo, slug="myresources")
    
    @Command()
    def custom_action(self, 
                     name: args.NAME,
                     value: args.VALUE = None) -> dict:
        """Perform a custom action on the resource.
        
        Detailed explanation of what this command does.
        
        Usage: CLI Usage
          ```sh
          duploctl myresource custom_action <name> --value <value>
          ```
        
        Args:
          name: The name of the resource to act on.
          value: Optional value for the action.
        
        Returns:
          message: A success message with details.
        
        Raises:
          DuploError: If the resource is not found or action fails.
        """
        response = self.duplo.post(self.endpoint(name, "action"), {"value": value})
        return response.json()
```

## Type Hints Best Practices

- Always use type hints for function parameters and return values
- Use `typing` module for complex types
- Use `Optional[T]` for nullable types
- Use `Union[T1, T2]` for multiple possible types
- Use `List[T]`, `Dict[K, V]`, `Tuple[T, ...]` for collections

```python
from typing import Optional, List, Dict, Union

def process_data(
    items: List[str],
    config: Optional[Dict[str, Any]] = None
) -> Union[Dict[str, str], None]:
    """Process a list of items with optional configuration."""
    if config is None:
        config = {}
    # Implementation
    return {"status": "processed"}
```

## Error Handling

- Use specific exception types from `duplocloud.errors`
- Always include helpful error messages
- Provide context in error messages (include resource names, IDs, etc.)

```python
from duplocloud.errors import DuploError, DuploFailedResource

def find_resource(name: str) -> dict:
    """Find a resource by name."""
    try:
        result = [r for r in self.list() if r["Name"] == name][0]
    except IndexError:
        raise DuploError(f"Resource '{name}' not found", 404)
    except KeyError as e:
        raise DuploError(f"Invalid resource structure: missing {e}")
    return result
```

## Lazy Loading Pattern

For tenant-scoped resources, properties should be lazy-loaded:

```python
@property
def tenant(self):
    """Lazy-load tenant information."""
    if not self._tenant:
        self._tenant = self.tenant_svc.find()
        self._tenant_id = self._tenant["TenantId"]
    return self._tenant
```

## Command Decorator Usage

- Use `@Command()` for all public methods that should be CLI commands
- Use `@Command("alias1", "alias2")` for command aliases
- Function signature determines CLI arguments automatically
- Use `args.*` types for common parameters

```python
@Command("ls")  # Alias: "ls" in addition to "list"
def list(self) -> list:
    """Retrieve a list of resources."""
    response = self.duplo.get(self.endpoint("list"))
    return response.json()

@Command()
def create(self, 
          body: args.BODY,
          wait: args.WAIT = False) -> dict:
    """Create a new resource."""
    # Implementation
    pass
```

## When to Extend Base Classes

- **Don't extend anything**: For non-CRUD resources (e.g., `version`, `jit`, `system`)
- **Extend `DuploResourceV2`**: For CRUD resources on v2 API
- **Extend `DuploResourceV3`**: For CRUD resources on v3 API

```python
# Non-CRUD: No base class needed
@Resource("version")
class DuploVersion:
    def __init__(self, duplo: DuploClient):
        self.duplo = duplo
    
    def __call__(self) -> dict:
        return {"version": "1.0.0"}

# CRUD: Extend V2 or V3
@Resource("service", scope="tenant")
class DuploService(DuploResourceV2):
    def __init__(self, duplo: DuploClient):
        super().__init__(duplo)
```
