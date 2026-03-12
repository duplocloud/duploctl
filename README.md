# duploctl

[![Unit Tests](https://github.com/duplocloud/duploctl/actions/workflows/test_unit.yml/badge.svg)](https://github.com/duplocloud/duploctl/actions/workflows/test_unit.yml) [![PyPI - Version](https://img.shields.io/pypi/v/duplocloud-client?logo=pypi)](https://pypi.org/project/duplocloud-client/) [![Docker Image Version](https://img.shields.io/docker/v/duplocloud/duploctl?sort=semver&logo=Docker&label=docker&color=blue&link=https%3A%2F%2Fhub.docker.com%2Fr%2Fduplocloud%2Fduploctl)](https://hub.docker.com/r/duplocloud/duploctl) [![GitHub Release](https://img.shields.io/github/v/release/duplocloud/duploctl?logo=github&label=Github&color=purple)
](https://github.com/duplocloud/duploctl) [![Static Badge](https://img.shields.io/badge/Docs-lightblue?logo=github)
](https://cli.duplocloud.com/)

CLI and Python SDK for managing [DuploCloud](https://duplocloud.com/) infrastructure. Works as a standalone command-line tool or as a Python module in your own scripts and CI/CD pipelines.

- **30+ resource types** -- tenants, services, infrastructure, hosts, RDS, S3, Lambda, ECS, Batch, Argo Workflows, and more
- **Plugin architecture** -- resources discovered via Python entry points, easy to extend
- **Multiple output formats** -- JSON (default), YAML, CSV, env vars, string
- **JMESPath queries** -- filter and reshape output with `-q`
- **Interactive login** -- browser-based OAuth flow with token caching
- **Model validation** -- optional Pydantic validation against DuploCloud SDK schemas

## Installation

```sh
pip install duplocloud-client
```

```sh
brew install duplocloud/tap/duploctl
```

For pinned version installs and alternative methods (GitHub release, git tag, Docker, standalone binary), see the [release notes](https://github.com/duplocloud/duploctl/releases/latest).

## Quick Start

Set your DuploCloud credentials:

```sh
export DUPLO_HOST=https://example.duplocloud.net
export DUPLO_TOKEN=AQAAA...
export DUPLO_TENANT=dev01
```

Run commands:

```sh
# List services in the current tenant
duploctl service list

# Find a specific tenant
duploctl tenant find mytenant

# Create a service from a YAML file
duploctl service create -f service.yaml

# Get output as YAML
duploctl service list -o yaml

# Filter output with JMESPath
duploctl service list -q '[].Name'
```

## Configuration

| Flag | Env Variable | Default | Description |
|---|---|---|---|
| `--host`, `-H` | `DUPLO_HOST` | -- | DuploCloud portal URL (required) |
| `--token`, `-t` | `DUPLO_TOKEN` | -- | Authentication token (required unless using `-I`) |
| `--tenant`, `-T` | `DUPLO_TENANT` | -- | Tenant name |
| `--output`, `-o` | `DUPLO_OUTPUT` | `json` | Output format (`json`, `yaml`, `csv`, `env`, `string`) |
| `--query`, `-q` | -- | -- | JMESPath query to filter output |
| `--wait`, `-w` | -- | `false` | Wait for async operations to complete |
| `--file`, `-f` | -- | -- | YAML/JSON file for resource body input |
| `--interactive`, `-I` | -- | `false` | Use interactive browser-based login |
| `--admin`, `--isadmin` | -- | `false` | Request admin JIT credentials (use with `-I`) |
| `--log-level`, `-L` | `DUPLO_LOG_LEVEL` | `INFO` | Log level |
| `--config-file` | `DUPLO_CONFIG` | -- | Path to duploctl config file |
| `--ctx` | `DUPLO_CONTEXT` | -- | Named context from config file |
| `--validate` | `DUPLO_VALIDATE` | `false` | Validate inputs against SDK model schemas |
| `--dry-run` | -- | `false` | Print changes without submitting |

Full argument reference: [cli.duplocloud.com/Args](https://cli.duplocloud.com/Args/)

## CLI Usage

```
duploctl <resource> <command> [args...]
```

### Cloud Access (JIT)

```sh
# Configure AWS credentials
duploctl jit update_aws_config myportal

# Open AWS web console
duploctl jit web

# Get Kubernetes config
duploctl jit update_kubeconfig myinfra
```

### Resource Management

```sh
# Infrastructure and tenants
duploctl infrastructure list
duploctl tenant find mytenant

# Services
duploctl service list
duploctl service create -f service.yaml -w
duploctl service update_image myservice nginx:latest

# Kubernetes resources
duploctl configmap list
duploctl secret find mysecret
duploctl cronjob list
duploctl pod list

# AWS resources
duploctl rds list
duploctl s3 list
duploctl lambda list
duploctl hosts list
```

## Python Module

Use `duploctl` programmatically in your own scripts.

### From Environment Variables

```python
from duplocloud.controller import DuploCtl

# Reads DUPLO_HOST, DUPLO_TOKEN, DUPLO_TENANT from env
duplo, args = DuploCtl.from_env()

# Callable interface (like CLI syntax)
services = duplo("service", "list")
tenant = duplo("tenant", "find", "mytenant")
```

### From Explicit Credentials

```python
from duplocloud.controller import DuploCtl

duplo = DuploCtl.from_creds(
    host="https://example.duplocloud.net",
    token="AQAAA...",
    tenant="dev01",
)

# Load a resource and call methods directly
svc = duplo.load("service")
services = svc.list()
my_service = svc.find("myservice")

# JMESPath filtering
names = duplo("service", "list", query="[].Name")
```

### Create Resources

```python
duplo = DuploCtl.from_creds(host="...", token="...", tenant="dev01")

# Create from a dict
duplo("service", "create", body={
    "Name": "myservice",
    "Image": "nginx:latest",
    "Replicas": 2,
})

# Or load the resource directly
svc = duplo.load("service")
svc.create(body={"Name": "myservice", "Image": "nginx:latest"})
```

## Docker

```sh
# Run any duploctl command
docker run -e DUPLO_HOST=... -e DUPLO_TOKEN=... -e DUPLO_TENANT=... \
  duplocloud/duploctl service list

# Output as YAML
docker run -e DUPLO_HOST=... -e DUPLO_TOKEN=... -e DUPLO_TENANT=... \
  duplocloud/duploctl service list -o yaml
```

## CI/CD

`duploctl` integrates with all major CI/CD platforms. See the [DuploCloud CI/CD docs](https://docs.duplocloud.com/docs/automation-platform/introduction-to-ci-cd) for detailed guides.

| Platform | Project | Marketplace |
|----------|---------|-------------|
| [GitHub Actions](https://docs.duplocloud.com/docs/automation-platform/introduction-to-ci-cd/github-actions) | [duplocloud/actions](https://github.com/duplocloud/actions) | [Marketplace](https://github.com/marketplace/actions/duplocloud) |
| [Bitbucket Pipelines](https://docs.duplocloud.com/docs/automation-platform/introduction-to-ci-cd/bitbucket-pipelines) | [duplocloud/duploctl-pipe](https://github.com/duplocloud/duploctl-pipe) | |
| [CircleCI](https://docs.duplocloud.com/docs/automation-platform/introduction-to-ci-cd) | [duplocloud/orbs](https://github.com/duplocloud/orbs) | [Orb Registry](https://circleci.com/developer/orbs/orb/duplocloud/orbs) |
| [GitLab CI](https://docs.duplocloud.com/docs/automation-platform/introduction-to-ci-cd/gitlab-ci-cd) | [duplocloud/ci](https://gitlab.com/duplocloud/ci) | [CI/CD Catalog](https://gitlab.com/explore/catalog/duplocloud/ci) |

## Development

```sh
git clone --recurse-submodules https://github.com/duplocloud/duploctl.git
cd duploctl
pip install -e '.[build,test,aws,docs]'
pytest src -m unit
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full development guidelines.

## Resources

- [Documentation](https://cli.duplocloud.com/) -- full CLI reference, resource guides, and API docs
- [Changelog](https://cli.duplocloud.com/Changelog) -- version history
- [GitHub Releases](https://github.com/duplocloud/duploctl/releases) -- install artifacts and release notes
- [PyPI](https://pypi.org/project/duplocloud-client/) -- Python package
- [Docker Hub](https://hub.docker.com/r/duplocloud/duploctl) -- container images
- [DuploCloud](https://duplocloud.com/) -- platform documentation
