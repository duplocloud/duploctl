# Duplocloud Py Client  

![Tests](https://github.com/duplocloud/duploctl/actions/workflows/test.yml/badge.svg) ![PyPI - Version](https://img.shields.io/pypi/v/duplocloud-client)


A package to spawn service clients for working with Duplocloud. This is a cli for interacting with duplocloud resources. This is great within cli pipelines. Built to be as extensible as possible and can be used as normal python module as well as cli. 

## Installation  

From PyPi:
```
pip install duplocloud-client
```

## Usage 

This project may bes used as a cli or as a python module in your own unique script. 

### Configuration  

The following inputs are global:  
| Arg | Env Var | Description | Default | Required |  
| --- | --- | --- | --- | --- |
| --host, -H | DUPLO_HOST | The host to connect to |  | Yes |
| --token, -T | DUPLO_TOKEN | The token to use for auth |  | Yes |
| --tenant, -t | DUPLO_TENANT | The tenant to use for auth | default | No | 

### CLI  

Here is a quick template on how the cli breaks down. 

```sh
duploctl <resource> <command> <args...>
```

### Python Module

Here is how to spawn your own client the quick way from args and env. 

```python
duplo = DuploClient.from_env()
out = duplo.run("tenant", "list")
```

Here we show how to spawn a client with a custom host and token. 

```python
duplo = DuploClient(host="https://example.duplocloud.com", token="mytoken")
svc = duplo.load("tenant")
t = svc.find("mytenant")
print(t)
```
