# Duplocloud Py Client  

[![Tests](https://github.com/duplocloud/duploctl/actions/workflows/test.yml/badge.svg)](https://github.com/duplocloud/duploctl/actions/workflows/test.yml) [![PyPI - Version](https://img.shields.io/pypi/v/duplocloud-client)](https://pypi.org/project/duplocloud-client/)


```duploctl``` is a package that spawns service clients that work with Duplocloud. It is a CLI for interacting with Duplocloud resources, such as Tenants, and is designed to work seamlessly within CLI-based CI/CD pipelines. It is a fully extensible package and can be used as both a Python module and a CLI. 

## Installation  

From PyPi:
```
pip install duplocloud-client
```

## Usage 

Use ```duploctl``` as a CLI or as a standalone Python module called by your custom script. 

### Configuration  

Use the following syntax for these global arguments:  
| Arg | Env Var | Description | Default | Required |  
| --- | --- | --- | --- | --- |
| --host, -H | DUPLO_HOST | The host to connect to |  | Yes |
| --token, -T | DUPLO_TOKEN | The token to use for auth |  | Yes |
| --tenant, -t | DUPLO_TENANT | The tenant to use for auth | default | No | 

### CLI  

CLI command syntax for invoking ```duploctl``` 

```sh
duploctl <resource> <command> <args...>
```

### Example Usages

Full documentation is in the Wiki section.

Configure `duploctl` access with environment variables:
```sh
export DUPLO_HOST=https://example.duplocloud.net
export DUPLO_TOKEN=AQAAA...
export DUPLO_TENANT=dev01
```

List the services in a tenant:
```sh
duploctl service list
```

Get AWS Console URL:
```sh
duploctl jit aws
```

Get Kubernetes config:
```sh
duploctl jit update_kubeconfig myinfra
```

### Python Module

Spawn your client from a Python script using the ```DuploClient.from_env()``` method and arguments. The second return value are the unparsed arguments from the command line. This example uses the client as a callable using command like syntax.

```python
duplo, args = DuploClient.from_env()
t = duplo("tenant", "find", "mytenant")
print(t)
```

Spawn a client with a custom host and token from a Python script. This example loads a resource and runs a method manually. 

```python
duplo = DuploClient.from_creds(host="https://example.duplocloud.net", token="mytoken")
tenants = duplo.load("tenant")
t = tenants.find("mytenant")
print(t)
```

