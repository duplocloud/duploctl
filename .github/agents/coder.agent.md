---
description: 'Implement code for duploctl resources and features'
tools: ['runCommands', 'runTasks', 'edit', 'search', 'new', 'todos', 'runTests', 'usages', 'problems', 'changes', 'testFailure']
---

# Coder Mode

Implement code for duploctl following established patterns and architecture.

## Requirements

- Always use the README.md for context about the project
- Always use the CONTRIBUTING.md for context about the project  
- Follow the architecture patterns from `.github/copilot-instructions.md`
- Use VS Code tasks instead of direct terminal commands
- Write tests for new features
- Update CHANGELOG.md with changes

## Resource Implementation Checklist

When creating a new resource:

1. **Determine Resource Type**
   - [ ] CRUD resource (needs V2 or V3 base class)
   - [ ] Non-CRUD resource (no base class needed)
   - [ ] Portal-scoped or tenant-scoped

2. **Create Resource File**
   - [ ] Create `src/duplo_resource/myresource.py`
   - [ ] Add imports at top of file
   - [ ] Decorate with `@Resource(name, scope="portal"|"tenant")`
   - [ ] Extend appropriate base class if CRUD
   - [ ] Implement `__init__` accepting `DuploClient`

3. **Implement Commands**
   - [ ] Decorate methods with `@Command()`
   - [ ] Use type hints with `args.*` types
   - [ ] Write Google-style docstrings with CLI examples
   - [ ] Return dict or list for automatic formatting
   - [ ] Raise `DuploError` for error conditions

4. **Register Entry Point**
   - [ ] Add to `pyproject.toml` under `[project.entry-points."duplocloud.net"]`
   - [ ] Format: `name = "duplo_resource.module:ClassName"`

5. **Write Tests**
   - [ ] Create test file in `src/tests/`
   - [ ] Use `@pytest.mark.unit` for unit tests
   - [ ] Test all command methods
   - [ ] Run tests with `pytest src -m unit`

6. **Update Documentation**
   - [ ] Add entry to CHANGELOG.md under `[Unreleased]`
   - [ ] Include CLI examples in docstrings
   - [ ] Document any special behavior or requirements

## Code Patterns

### CRUD Resource (V2 API)

```python
from duplocloud.client import DuploClient
from duplocloud.resource import DuploResourceV2
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("myresource", scope="tenant")
class DuploMyResource(DuploResourceV2):
    """Manage MyResource resources in DuploCloud.
    
    Provides commands to create, read, update, and delete MyResource
    resources within a tenant.
    """
    
    def __init__(self, duplo: DuploClient):
        super().__init__(duplo)
    
    # V2 base class provides list(), find(), apply()
    # Add custom commands as needed
```

### CRUD Resource (V3 API)

```python
from duplocloud.client import DuploClient
from duplocloud.resource import DuploResourceV3
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("myresource", scope="tenant")
class DuploMyResource(DuploResourceV3):
    """Manage MyResource resources using V3 API."""
    
    def __init__(self, duplo: DuploClient):
        super().__init__(duplo, slug="myresources")
    
    # V3 base class provides list(), find(), create(), update(), delete(), apply()
    # Override or add custom commands as needed
```

### Non-CRUD Resource

```python
from duplocloud.client import DuploClient
from duplocloud.commander import Command, Resource

@Resource("mytool")
class DuploMyTool:
    """Custom tool for specialized operations."""
    
    def __init__(self, duplo: DuploClient):
        self.duplo = duplo
    
    @Command()
    def analyze(self) -> dict:
        """Run analysis on portal data.
        
        Usage: CLI Usage
          ```sh
          duploctl mytool analyze
          ```
        
        Returns:
          results: Analysis results.
        """
        # Implementation
        return {"status": "complete"}
```

## Workflow

1. Read requirements and understand what resource/feature is needed
2. Check existing similar resources for patterns
3. Create resource file with proper structure
4. Implement commands with proper decorators and docstrings
5. Register in pyproject.toml
6. Write unit tests
7. Run tests with VS Code task "Unit Test"
8. Update CHANGELOG.md
9. Verify with lint task if needed
