---
description: 'YAML coding conventions and guidelines'
applyTo: '**/*.yaml, **/*.yml'
---

# YAML Coding Conventions

Use YAML best practices to format YAML files correctly.

## General Instructions

- YAML arrays should be aligned with the parent key versus two spaces in
  - Example:
    ```yaml
    fruits:
    - apple
    - banana
    - cherry
    ```
- Use spaces instead of tabs for indentation (2 spaces per level).
- Maintain consistent indentation throughout the file.
- Use lowercase letters for keys and separate words with underscores or hyphens.
- Don't use double or single quotes unless the string has special characters or starts with a number
- Use comments (`#`) to explain complex sections or provide context.

## DuploCloud Resource YAML Format

When creating resource definition files:

```yaml
# Service definition example
Name: myservice
Image: nginx:latest
Replicas: 2
Volumes:
- Name: data
  Path: /data
ExtraConfig: |
  worker_processes auto;
  events {
    worker_connections 1024;
  }
```

## Entry Points in pyproject.toml

Resources must be registered in `pyproject.toml`:

```toml
[project.entry-points."duplocloud.net"]
infrastructure = "duplo_resource.infrastructure:DuploInfrastructure"
tenant = "duplo_resource.tenant:DuploTenant"
service = "duplo_resource.service:DuploService"
myresource = "duplo_resource.myresource:DuploMyResource"
```

**Key Points:**
- Entry point name is the CLI resource name
- Value format: `"module_path:ClassName"`
- Module path relative to `src/` directory
- Class name must match decorated class

## Test Data YAML

Test fixtures should be in `src/tests/data/`:

```yaml
# src/tests/data/service.yaml
Name: test-service
Image: nginx:latest
Replicas: 1
Env:
- Name: ENV_VAR
  Value: test_value
```

## MkDocs Configuration

Documentation snippets can reference YAML files:

```markdown
Contents of the `service.yaml` file
```yaml
--8<-- "src/tests/data/service.yaml"
```
```

## Common Patterns

### Boolean Values
```yaml
enabled: true
disabled: false
```

### Lists
```yaml
# Inline style (for short lists)
ports: [80, 443, 8080]

# Block style (preferred for readability)
volumes:
- name: data
  path: /data
- name: config
  path: /config
```

### Multi-line Strings
```yaml
# Literal block (preserves newlines)
script: |
  #!/bin/bash
  echo "Hello"
  echo "World"

# Folded block (joins lines)
description: >
  This is a long description
  that spans multiple lines
  but will be joined.
```

### Dictionaries
```yaml
metadata:
  name: myresource
  labels:
    app: myapp
    env: prod
```

## Validation

- Use YAML linters to validate syntax
- Test resource definitions with `duploctl <resource> create -f file.yaml --dry-run` if supported
- Keep test data minimal and focused on specific test cases
