from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args
from datetime import datetime, timedelta
import os
from pathlib import Path
import yaml

@Resource("jit")
class DuploJit(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    
  @Command()
  def aws(self):
    """Retrieve aws session credentials for current user."""
    sts = self.duplo.get("adminproxy/GetJITAwsConsoleAccessUrl")
    return sts.json()

  @Command()
  def k8s(self,
          planId: args.PLAN = None):
    """Retrieve k8s session credentials for current user."""
    creds = self.duplo.get(f"v3/admin/plans/{planId}/k8sConfig")
    return self.__k8s_exec_credential(creds.json())
  
  @Command()
  def update_kubeconfig(self,
                        planId: args.PLAN = None):
    """Update kubeconfig"""
    # first get the kubeconfig file and parse it
    kubeconfig_path = os.environ.get("KUBECONFIG", f"{Path.home()}/.kube/config")
    kubeconfig = (yaml.safe_load(open(kubeconfig_path, "r")) 
                  if os.path.exists(kubeconfig_path) 
                  else self.__empty_kubeconfig())
    # load the cluster config info
    infra = self.duplo.load("infrastructure")
    conf = infra.eks_config(planId)
    conf["Name"] = conf["Name"].removeprefix("duploinfra-")
    # add the cluster, user, and context to the kubeconfig
    self.__add_to_kubeconfig("clusters", self.__cluster_config(conf), kubeconfig)
    self.__add_to_kubeconfig("users", self.__user_config(conf), kubeconfig)
    self.__add_to_kubeconfig("contexts", self.__context_config(conf), kubeconfig)
    kubeconfig["current-context"] = conf["Name"]
    # write the kubeconfig back to the file
    with open(kubeconfig_path, "w") as f:
      yaml.safe_dump(kubeconfig, f)
    return {"message": f"kubeconfig updated successfully to {kubeconfig_path}"}
  
  def __k8s_exec_credential(self, creds):
    expiration = creds.get("LastTokenRefreshTime", datetime.now() + timedelta(seconds=60*55))
    return {
      "kind": "ExecCredential",
      "apiVersion": "client.authentication.k8s.io/v1beta1",
      "spec": {
        "cluster": {
          "server": creds["ApiServer"],
          "certificate-authority-data": creds["CertificateAuthorityDataBase64"],
          "config": None
        },
        "interactive": False
      },
      "status": {
        "token": creds["Token"],
        "expirationTimestamp": expiration
      }
    }
  
  def __cluster_config(self, config):
    """Build a kubeconfig cluster object"""
    return {
      "name": config["Name"],
      "cluster": {
        "server": config["ApiServer"],
        "certificate-authority-data": config["CertificateAuthorityDataBase64"]
      }
    }
  
  def __user_config(self, config):
    """Build a kubeconfig user object"""
    return {
      "name": config["Name"],
      "user": {
        "exec": {
          "apiVersion": "client.authentication.k8s.io/v1beta1",
          "installHint": """
Install duploctl for use with kubectl by following
https://github.com/duplocloud/duploctl
""",
          "command": "duploctl",
          "env": [{
            "name": "DUPLO_HOST",
            "value": self.duplo.host
          },{
            "name": "DUPLO_TOKEN",
            "value": self.duplo.headers["Authorization"].split(" ")[1]
          }],
          "args": [
            "jit",
            "k8s",
            "--plan",
            config["Name"]
          ]
        }
      }
    }
  
  def __context_config(self, config):
    """Build a kubeconfig context object"""
    return {
      "name": config["Name"],
      "context": {
        "cluster": config["Name"],
        "user": config["Name"]
      }
    }
  
  def __add_to_kubeconfig(self, section, item, kubeconfig):
    """Add an item to a kubeconfig section if it is not already present"""
    if item not in kubeconfig[section]:
      kubeconfig[section].append(item)

  def __empty_kubeconfig(self):
    return {
      "apiVersion": "v1",
      "kind": "Config",
      "preferences": {},
      "clusters": [],
      "users": [],
      "contexts": []
    }
