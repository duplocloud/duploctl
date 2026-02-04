# GitHub Copilot Instructions for duploctl

## Project Overview

`duploctl` is a **CLI and Python package** for interacting with DuploCloud portals. It provides a command-line interface and extensible Python module for managing DuploCloud resources (Tenants, Services, Infrastructure, etc.) within CI/CD pipelines and interactive workflows.

**Key Characteristics:**
- **Dual Interface**: Works as both a CLI (`duploctl <resource> <command>`) and Python module
- **Plugin Architecture**: Uses Python entry points for dynamic resource loading
- **Decorator-Based**: `@Resource` and `@Command` decorators register resources and commands
- **Scope System**: Resources can be portal-scoped or tenant-scoped with automatic injection
- **API Versioning**: Supports v1, v2, and v3 DuploCloud API endpoints with appropriate base classes
- **CRUD Patterns**: V2/V3 base classes provide standardized CRUD operations for applicable resources

## Core Architecture

### Resource Registration System

Resources are registered via **entry points** in `pyproject.toml` and decorated classes:

```toml
[project.entry-points."duplocloud.net"]
tenant = "duplo_resource.tenant:DuploTenant"
service = "duplo_resource.service:DuploService"
infrastructure = "duplo_resource.infrastructure:DuploInfrastructure"
```

Each resource class must:
1. Be decorated with `@Resource(name, scope="portal"|"tenant")`
2. Accept `DuploClient` in `__init__`
3. Define commands using `@Command()` decorator
4. Be registered in `pyproject.toml` entry points

### Decorator Pattern

#### `@Resource(name: str, scope: str = "portal")`

Registers a class as a resource and optionally injects scope-specific functionality.

**Parameters:**
- `name`: Resource name (used in CLI: `duploctl <name> ...`)
- `scope`: Either `"portal"` (default) or `"tenant"`

**Scope Behaviors:**
- **Portal scope**: Resource operates at portal level, no tenant context required
- **Tenant scope**: Automatically injected with:
  - `tenant` property (lazy-loaded tenant object)
  - `tenant_id` property (lazy-loaded tenant ID)
  - `prefix` property (returns `duploservices-{tenant_name}-`)
  - `prefixed_name(name)` method (prepends tenant prefix)
  - `endpoint()` method (tenant-aware endpoint builder)

#### `@Command(*aliases)`

Registers a method as an executable command. Arguments are automatically parsed from function signature using type hints.

```python
@Command()
def create(self, body: args.BODY, wait: args.WAIT = False) -> dict:
    """Create a resource."""
    # Implementation
```

### Base Classes and API Versions

**When to extend base classes:**
- Only extend `DuploResourceV2` or `DuploResourceV3` if the resource has **CRUD operations** (find, create, update, delete, apply)
- Resources with only custom methods (like `version`, `jit`, `system`, `plan`) should **not extend anything** - just use `@Resource` decorator

**Base Class Hierarchy:**

1. **`DuploResource`** (v1 API - base class)
   - Default `api_version = "v1"`
   - Minimal functionality: `wait()`, `command()`, `__call__()`
   - Use for: Non-CRUD resources like `jit`, `system`, `plan`, `version`

2. **`DuploResourceV2`** (v2 API)
   - Default `api_version = "v2"`
   - Provides: `list()`, `find()`, `apply()` commands
   - Portal endpoint: `endpoint(path)` returns `path`
   - Tenant endpoint: `endpoint(path)` returns `subscriptions/{tenant_id}/{path}`
   - Use for: CRUD resources on v2 API (e.g., `user`, `infrastructure`, `asg`, `hosts`, `lambda`)

3. **`DuploResourceV3`** (v3 API)
   - Default `api_version = "v3"`
   - Provides: `list()`, `find()`, `create()`, `update()`, `delete()`, `apply()` commands
   - Portal endpoint: `endpoint(name, path)` returns `v3/{slug}/{name}/{path}`
   - Tenant endpoint: `endpoint(name, path)` returns `v3/subscriptions/{tenant_id}/{slug}/{name}/{path}`
   - Use for: CRUD resources on v3 API (e.g., `configmap`, `secret`, `batch_*`, `cloudfront`)

**Endpoint Method Behavior:**

The `endpoint()` method is **version-aware** and **scope-aware**:

```python
# V2 Portal: endpoint(path)
self.endpoint("mypath")  # → "mypath"

# V2 Tenant: endpoint(path)
self.endpoint("mypath")  # → "subscriptions/{tenant_id}/mypath"

# V3 Portal: endpoint(name, path)
self.endpoint("myresource", "details")  # → "v3/{slug}/myresource/details"

# V3 Tenant: endpoint(name, path)
self.endpoint("myresource", "details")  # → "v3/subscriptions/{tenant_id}/{slug}/myresource/details"
```

### Tenant Scope Injection Pattern

When `@Resource(scope="tenant")` is used, the decorator **dynamically injects** tenant functionality using a **mixin pattern** (`_inject_tenant_scope`):

1. Wraps `__init__` to add private attributes (`_tenant`, `_tenant_id`)
2. Injects lazy-loading properties using `setattr()`
3. Overrides `endpoint()` method with tenant-aware version
4. No deep inheritance required - clean separation of concerns

**Why this matters:**
- Avoids deep inheritance hierarchies
- Properties are lazy-loaded (no API calls until accessed)
- Single decorator parameter controls behavior
- Works across V2 and V3 APIs consistently

## Critical Files and Locations

### Core Framework Files

- **`src/duplocloud/commander.py`**: 
  - Contains `@Resource` and `@Command` decorators
  - Maintains `schema` and `resources` registries
  - Implements `_inject_tenant_scope()` mixin function
  - Provides `commands_for(name)` to retrieve all commands for a resource (including parent class)
  - Entry point loading via `importlib.metadata.entry_points`

- **`src/duplocloud/resource.py`**:
  - Base classes: `DuploResource`, `DuploResourceV2`, `DuploResourceV3`
  - Default CRUD command implementations
  - `wait()` method for async operation polling
  - Portal-scoped `endpoint()` methods (overridden by tenant injection)

- **`src/duplocloud/client.py`**:
  - `DuploClient` class - main client interface
  - Configuration management (`from_env()`, `from_creds()`)
  - HTTP methods with caching (`get()`, `post()`, `put()`, `delete()`)
  - Resource loading via `load(name)` method
  - JMESPath query support, output formatting

- **`src/duplocloud/args.py`**:
  - Type-annotated argument definitions for argparse
  - Common arguments: `NAME`, `BODY`, `WAIT`, `TENANT`, etc.
  - Used in `@Command` decorated methods for automatic CLI generation

- **`src/duplocloud/cli.py`**:
  - Entry point for CLI (`duploctl` command)
  - Argument parsing and command routing

### Resource Implementation Files

- **`src/duplo_resource/`**: Directory containing all resource implementations
  - Each file defines one resource class
  - Must be registered in `pyproject.toml` entry points
  - Examples: `tenant.py`, `service.py`, `infrastructure.py`, `lambda.py`, etc.

### Configuration and Build Files

- **`pyproject.toml`**: 
  - Project metadata and dependencies
  - **Entry points** for resources (`duplocloud.net`) and formats (`formats.duplocloud.net`)
  - Script entry points (`[project.scripts]`)
  - Build system configuration
  - Test markers and coverage settings

- **`.vscode/tasks.json`**: Predefined VS Code tasks (Pip Install, Unit Test, Docs Build, etc.)
- **`.devcontainer.json`**: Dev container configuration for consistent environment

## Development Patterns

### Creating a New CRUD Resource

1. **Determine API version and scope:**
   ```python
   # V3 tenant-scoped resource with CRUD
   from duplocloud.resource import DuploResourceV3
   from duplocloud.commander import Resource, Command
   import duplocloud.args as args
   
   @Resource("myresource", scope="tenant")
   class DuploMyResource(DuploResourceV3):
       def __init__(self, duplo):
           super().__init__(duplo, slug="myresources")  # slug for API path
   ```

2. **Add custom commands if needed:**
   ```python
   @Command()
   def custom_action(self, name: args.NAME, value: args.VALUE) -> dict:
       """Perform a custom action."""
       # Tenant-scoped endpoint automatically available
       response = self.duplo.post(self.endpoint(name, "action"), {"value": value})
       return response.json()
   ```

3. **Register in `pyproject.toml`:**
   ```toml
   [project.entry-points."duplocloud.net"]
   myresource = "duplo_resource.myresource:DuploMyResource"
   ```

### Creating a Non-CRUD Resource

For resources that don't follow CRUD patterns:

```python
from duplocloud.client import DuploClient
from duplocloud.commander import Resource, Command

@Resource("mytool")  # No base class needed!
class DuploMyTool:
    def __init__(self, duplo: DuploClient):
        self.duplo = duplo
    
    @Command()
    def analyze(self) -> dict:
        """Run custom analysis."""
        return {"status": "analyzed"}
```

### Command Pattern Best Practices

- Use Google-style docstrings with CLI usage examples
- Include type hints for automatic argparse generation
- Use `args.*` types for common parameters
- Return dictionaries or lists (automatically formatted by CLI)
- Raise `DuploError` for error conditions

```python
@Command()
def create(self, body: args.BODY, wait: args.WAIT = False) -> dict:
    """Create a resource.
    
    Usage: CLI Usage
      ```sh
      duploctl myresource create -f 'resource.yaml'
      ```
    
    Args:
      body: The resource definition.
      wait: Wait for resource to be ready.
    
    Returns:
      message: Success message.
    
    Raises:
      DuploError: If creation fails.
    """
    # Implementation
```

## Testing Guidelines

- Unit tests in `src/tests/` with `@pytest.mark.unit` decorator
- Integration tests with `@pytest.mark.integration` (create real resources!)
- Run unit tests: `pytest src -m unit`
- Test markers: `unit`, `integration`, `aws`, `gcp`, `azure`, `k8s`, `ecs`, `native`
- Coverage configured in `pyproject.toml` to omit test files

## VS Code Tasks

**Always prefer using VS Code tasks over direct CLI commands:**

- `Pip Install`: Full dev environment setup with editable install
- `Unit Test`: Run unit tests with pytest
- `Ruff Lint`: Lint source code
- `Build Package`: Build pip package
- `Docs Serve`: Run MkDocs local server
- `Docs Build`: Build documentation

**Use the task runner instead of terminal commands to ensure correct environment.**

## Documentation Standards

### Google-Style Docstrings

```python
def my_function(param1: str, param2: int) -> dict:
    """Single-line title of what the function does.
    
    Detailed description paragraph explaining the function's purpose,
    behavior, and any important notes.
    
    Usage: CLI Usage
      ```sh
      duploctl resource command <param1> <param2>
      ```
    
    Args:
      param1: Description of param1.
      param2: Description of param2.
    
    Returns:
      message: Description of return value.
    
    Raises:
      DuploError: When and why this error is raised.
    """
    return {}
```

**Key Points:**
- Title on first line after `"""`
- One blank line between sections
- Don't repeat type hints in docstring (already in signature)
- Include CLI usage examples for commands
- Use MkDocs snippets: `` --8<-- "src/tests/data/example.yaml" ``

## Python Coding Standards

### General Conventions

- Follow **PEP 8** style guide
- Use 4 spaces for indentation
- Maximum line length: 79 characters
- **Imports at top of file** - never inside functions or code blocks
- Use type hints for all function signatures
- Use `typing` module for complex types (`List[str]`, `Dict[str, Any]`, etc.)

### Import Organization

```python
# Standard library imports
import os
import sys
from pathlib import Path

# Third-party imports
import requests
import yaml

# Local imports
from duplocloud.client import DuploClient
from duplocloud.resource import DuploResourceV2
from duplocloud.commander import Command, Resource
import duplocloud.args as args
```

### Error Handling

- Use `DuploError` for domain-specific errors
- Use `DuploFailedResource` for resource creation/update failures
- Use `DuploStillWaiting` for wait timeout scenarios
- Always include helpful error messages

```python
from duplocloud.errors import DuploError

if resource not found:
    raise DuploError(f"Resource '{name}' not found", 404)
```

## Configuration and Authentication

### Environment Variables

- `DUPLO_HOST`: Portal URL (e.g., `https://example.duplocloud.net`)
- `DUPLO_TOKEN`: Authentication token
- `DUPLO_TENANT`: Tenant name (default: "default")
- `DUPLO_HOME`: Config directory (default: `~/.duplo`)
- `DUPLO_CONFIG`: Config file path
- `DUPLO_CACHE`: Cache directory

### .envrc Example (for direnv)

```sh
layout python3
PATH_add ./scripts

export DUPLO_HOME="config"
export KUBECONFIG="${DUPLO_HOME}/kubeconfig.yaml"
export AWS_CONFIG_FILE="${DUPLO_HOME}/aws"
export DUPLO_CONFIG="${DUPLO_HOME}/duploconfig.yaml"
export DUPLO_CACHE="${DUPLO_HOME}/cache"
```

## Build and Release Process

### Local Development

1. Clone with submodules: `git clone --recurse-submodules <repo>`
2. Install editable: `pip install --editable '.[build,test,aws,docs]'`
3. Run tests: `pytest src -m unit`

### Version Management

- Uses `setuptools_scm` for version determination from git tags
- Version bump workflow: `.github/workflows/publish.yml`
- Changelog must be updated before PR (CI checks for this)
- Signed commits required (GPG or 1Password)

### Building Artifacts

- Pip package: `python -m build`
- PyInstaller binary: `./scripts/installer.spec`
- Docker image: `docker compose build duploctl`
- Homebrew formula: `./scripts/formula.py <version>`

## Key Learnings from Architecture

### Scope System Design Decisions

1. **Mixin Pattern Over Deep Inheritance**: 
   - Avoids `DuploTenantResourceV2` and `DuploTenantResourceV3` classes
   - Single `scope="tenant"` parameter triggers dynamic injection
   - Cleaner class hierarchy, easier to maintain

2. **Runtime API Version Check**:
   - Single `endpoint()` method checks `self.api_version` at runtime
   - Avoids separate methods like `endpoint_v2()` and `endpoint_v3()`
   - Simplifies code, reduces duplication

3. **Lazy Loading**:
   - Tenant properties only fetch data when first accessed
   - Avoids unnecessary API calls for portal-scoped operations
   - Improves performance

4. **Decorator-Based Registration**:
   - Single source of truth for resource metadata
   - Scope enforcement at decoration time (raises `ValueError` for invalid scope)
   - Automatic registration in global `resources` dict

### Common Pitfalls to Avoid

1. **Don't use direct attribute assignment for methods** - Use `setattr()` in mixin injection
2. **Don't call APIs in `__init__`** - Use lazy properties instead
3. **Don't extend base classes for non-CRUD resources** - Just use `@Resource` decorator
4. **Don't forget to register in `pyproject.toml`** - Entry points are required
5. **Don't mix scope and inheritance** - Use decorator `scope` parameter, not separate classes
6. **Always import at file top** - Never import inside functions

## Cross-Reference with Related Projects

This project follows similar patterns to other DuploCloud projects:
- MCP server wrapper project uses same decorator patterns
- Shared Python conventions (Google docstrings, PEP 8, imports at top)
- Similar VS Code task organization
- Consistent documentation standards with MkDocs

## Quick Reference Commands

```sh
# Development
pip install --editable '.[build,test,aws,docs]'
pytest src -m unit
duploctl --help

# CLI Usage
export DUPLO_HOST=https://example.duplocloud.net
export DUPLO_TOKEN=AQAAA...
export DUPLO_TENANT=dev01
duploctl service list
duploctl jit update_aws_config myportal
duploctl jit web

# Python Usage
from duplocloud.client import DuploClient
duplo, args = DuploClient.from_env()
services = duplo.load("service")
s = services.find("myservice")
```
