from duplocloud.client import DuploClient
from duplocloud.errors import DuploError, DuploExpiredCache
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args
import os
from pathlib import Path
import yaml
import configparser
import webbrowser

@Resource("jit")
class DuploJit(DuploResource):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    
  @Command()
  def aws(self, nocache: bool = None):
    """Retrieve aws session credentials for current user."""
    sts = None
    k = self.duplo.cache_key_for("aws-creds")
    path = "adminproxy/GetJITAwsConsoleAccessUrl"
    nc = nocache if nocache is not None else self.duplo.nocache
    try:
      if nc:
        sts = self.duplo.get(path).json()
      else:
        sts = self.duplo.get_cached_item(k)
        if self.duplo.expired(sts.get("Expiration", None)):
          raise DuploExpiredCache(k)
    except DuploExpiredCache:
      sts = self.duplo.get(path).json()
      sts["Expiration"] = self.duplo.expiration()
      self.duplo.set_cached_item(k, sts)
    sts["Version"] = 1
    # TODO: Make the exp correct for aws cli because aws cli really doesn't like this format
    if "Expiration" in sts:
      del sts["Expiration"]
    return sts

  @Command()
  def k8s(self,
          planId: args.PLAN = None):
    """Retrieve k8s session credentials for current user."""
    if planId is None:
      raise DuploError("--plan is required")
    creds = None
    k = self.duplo.cache_key_for(f"plan,{planId},k8s-creds")
    path = f"v3/admin/plans/{planId}/k8sConfig"
    try:
      if self.duplo.nocache:
        response = self.duplo.get(path)
        creds = self.__k8s_exec_credential(response.json())
      else:
        creds = self.duplo.get_cached_item(k)
        exp = creds.get("status", {}).get("expirationTimestamp", None)
        if self.duplo.expired(exp):
          raise DuploExpiredCache(k)
    except DuploExpiredCache:
      response = self.duplo.get(path)
      creds = self.__k8s_exec_credential(response.json())
      self.duplo.set_cached_item(k, creds)
    # TODO: sadly the expirationTimestamp is not in the right format for kubectl either
    if "status" in creds and "expirationTimestamp" in creds["status"]:
      del creds["status"]["expirationTimestamp"]
    return creds
  
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
  
  @Command()
  def update_aws_config(self,
                        name: args.NAME):
    """Update aws config"""
    config = os.environ.get("AWS_CONFIG_FILE", f"{Path.home()}/.aws/config")
    cp = configparser.ConfigParser()
    cp.read(config)
    prf = f'profile {name}'
    msg = f"aws profile named {name} already exists in {config}"
    try:
      cp[prf]
    except KeyError:
      cmd = self.duplo.build_command("duploctl", "jit", "aws")
      cp.add_section(prf)
      cp.set(prf, 'region', os.getenv("AWS_DEFAULT_REGION", "us-west-2"))
      cp.set(prf, 'credential_process', " ".join(cmd))
      with open(config, 'w') as configfile:
        cp.write(configfile)
      msg = f"aws profile named {name} was successfully added to {config}"
    return {"message": msg}

  @Command()
  def web(self):
    b = self.duplo.browser
    wb = webbrowser if not b else webbrowser.get(b)
    sts = self.aws(nocache=True)
    wb.open(sts["ConsoleUrl"], new=0, autoraise=True)
    return {
      "message": "Opening AWS console in browser"
    }
  
  def __k8s_exec_credential(self, creds):
    cluster = {
      "server": creds["ApiServer"],
      "config": None
    }
    if creds["K8Provider"] == 0 and (ca := creds.get("CertificateAuthorityDataBase64", None)):
      cluster["certificate-authority-data"] = ca
    return {
      "kind": "ExecCredential",
      "apiVersion": "client.authentication.k8s.io/v1beta1",
      "spec": {
        "cluster": cluster,
        "interactive": False
      },
      "status": {
        "token": creds["Token"],
        "expirationTimestamp": self.duplo.expiration()
      }
    }
  
  def __cluster_config(self, config):
    """Build a kubeconfig cluster object"""
    cluster = {
      "server": config["ApiServer"]
    }
    if config["K8Provider"] == 0 and (ca := config.get("CertificateAuthorityDataBase64", None)):
      cluster["certificate-authority-data"] = ca
    elif config["K8Provider"] == 1:
      cluster["insecure-skip-tls-verify"] = True
    return {
      "name": config["Name"],
      "cluster": cluster
    }
  
  def __user_config(self, config):
    """Build a kubeconfig user object"""
    cmd = self.duplo.build_command("jit", "k8s", "--plan", config["Name"])
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
          "args": cmd
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
  

    
