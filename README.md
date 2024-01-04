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

### Python Module

Spawn your client from a Python script using the ```DuploClient.from_env()``` method and arguments. The second return value are the unparsed arguments from the command line. 

```python
duplo, args = DuploClient.from_env()
out = duplo.run("tenant", "list")
```

Spawn a client with a custom host and token from a Python script. 

```python
duplo = DuploClient(host="https://example.duplocloud.com", token="mytoken")
tenants = duplo.load("tenant")
t = tenants.find("mytenant")
print(t)
```

