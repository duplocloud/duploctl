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
    path = None
    k = self.duplo.cache_key_for("aws-creds")
    nc = nocache if nocache is not None else self.duplo.nocache

    # check if admin or choose tenant
    if self.duplo.isadmin:
      path = "adminproxy/GetJITAwsConsoleAccessUrl"
    else:
      t = self.duplo.load("tenant")
      tenant = t.find(self.duplo.tenant)
      path = f"subscriptions/{tenant['TenantId']}/GetAwsConsoleTokenUrl"
    
    # try and get those creds
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
    # either plan or tenant in cache key
    pt = planId if planId else self.duplo.tenant
    k = self.duplo.cache_key_for(f"plan,{pt},k8s-creds")
    creds = None
    try:
      if self.duplo.nocache:
        ctx = self.k8s_context(planId)
        creds = self.__k8s_exec_credential(ctx)
      else:
        creds = self.duplo.get_cached_item(k)
        exp = creds.get("status", {}).get("expirationTimestamp", None)
        if self.duplo.expired(exp):
          raise DuploExpiredCache(k)
    except DuploExpiredCache:
      ctx = self.k8s_context(planId)
      creds = self.__k8s_exec_credential(ctx)
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
    ctx = self.k8s_context(planId)
    if self.duplo.isadmin:
      ctx["Name"] = ctx["Name"].removeprefix("duploinfra-")
      ctx["cmd_arg"] = "--plan"
    else:
      ctx["Name"] = self.duplo.tenant
      ctx["cmd_arg"] = "--tenant"
    # add the cluster, user, and context to the kubeconfig
    self.__add_to_kubeconfig("clusters", self.__cluster_config(ctx), kubeconfig)
    self.__add_to_kubeconfig("users", self.__user_config(ctx), kubeconfig)
    self.__add_to_kubeconfig("contexts", self.__context_config(ctx), kubeconfig)
    kubeconfig["current-context"] = ctx["Name"]
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
  
  @Command()
  def k8s_context(self, 
                  planId: args.PLAN = None):
    """Get k8s context
    
    Gets context based on planId or tenant name or admin or nonadmin. 

    Args:
      planId (str): The planId of the infrastructure.
    
    Returns:
      dict: The k8s context.
    """
    tenant = None
    tenant_id = None
    tenant_name = self.duplo.tenant

    # don't even like try sometimes
    if not self.duplo.isadmin and not tenant_name:
      raise DuploError("--tenant is required", 300)
    if planId is None and not tenant_name:
      raise DuploError("--plan or --tenant is required", 300)
    
    # if we need to discover the planId or you are not admin, then we get the tenant
    if (planId is None and tenant_name) or not self.duplo.isadmin:
      tenant_svc = self.duplo.load("tenant")
      tenant = tenant_svc.find(tenant_name)
      planId = tenant.get("PlanID") if not planId else planId
      tenant_id = tenant.get("TenantId")

    # choose the correct path
    path = (f"v3/admin/plans/{planId}/k8sConfig"
            if self.duplo.isadmin
            else f"/v3/subscriptions/{tenant_id}/k8s/jitAccess")
    response = self.duplo.get(path)
    return response.json()
  
  def __k8s_exec_credential(self, ctx):
    cluster = {
      "server": ctx["ApiServer"],
      "config": None
    }
    if ctx["K8Provider"] == 0 and (ca := ctx.get("CertificateAuthorityDataBase64", None)):
      cluster["certificate-authority-data"] = ca
    return {
      "kind": "ExecCredential",
      "apiVersion": "client.authentication.k8s.io/v1beta1",
      "spec": {
        "cluster": cluster,
        "interactive": False
      },
      "status": {
        "token": ctx["Token"],
        "expirationTimestamp": self.duplo.expiration()
      }
    }
  
  def __cluster_config(self, ctx):
    """Build a kubeconfig cluster object"""
    cluster = {
      "server": ctx["ApiServer"]
    }
    if ctx["K8Provider"] == 0 and (ca := ctx.get("CertificateAuthorityDataBase64", None)):
      cluster["certificate-authority-data"] = ca
    elif ctx["K8Provider"] == 1:
      cluster["insecure-skip-tls-verify"] = True
    return {
      "name": ctx["Name"],
      "cluster": cluster
    }
  
  def __user_config(self, ctx):
    """Build a kubeconfig user object"""
    cmd = self.duplo.build_command("jit", "k8s", ctx["cmd_arg"], ctx["Name"])
    return {
      "name": ctx["Name"],
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
  
  def __context_config(self, ctx):
    """Build a kubeconfig context object"""
    return {
      "name": ctx["Name"],
      "context": {
        "cluster": ctx["Name"],
        "user": ctx["Name"],
        "namespace": ctx["DefaultNamespace"]
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
  

    
