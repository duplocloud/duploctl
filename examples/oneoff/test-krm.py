#!/usr/bin/env python3 

from duploctl_krm import common as c

def transform(krm):
    # yaml.safe_dump(res, sys.stderr, default_flow_style=False);
    configMap = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": krm["functionConfig"]["metadata"]["name"]
        },
        "data": {
            "message": krm["functionConfig"]["spec"]["message"]
        }
    }
    # c.mergeMeta(configMap, res["functionConfig"])
    krm["items"].append(configMap)
    # print(res["items"], file=sys.stderr)
    
    return krm

c.execute(transform)
