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
from datetime import datetime
import jwt

@Resource("jit")
class DuploJit(DuploResource):
  """Just In Time (JIT) Resource
  
  Just in time access for AWS. This will use Duplo credentials to ask a certain Duplo portal for temporary AWS credentials. These credentials will be valid for a certain amount of time and will be used to access AWS resources.

  Usage:  
    using the `duploctl` command line tool, you can manage services with actions:

    ```sh
    duploctl jit <action>
    ```
  """
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)

  @Command()
  def aws(self, nocache: bool = None):
    """AWS STS Session Credentials
    
    Provides a full sts session with credentials and region. The default return is a valid exec credential for the AWS CLI. The global `--admin` flag can be used to get the credentials for an admin, or else per tenant 
    credentials are returned. The `--interactive` flag can be used to get the credentials for an interactive session and use the cache. 

    Basic Usage:  
      ```sh
      duploctl jit aws
      ```

    Example: Using in AWS CLI Credential Process  
      Here is an example for using the duploctl jit for aws in an AWS CLI config file. 

      ```toml
      [profile myportal]
      region=us-west-2
      output=json
      credential_process=duploctl jit aws --host https://myportal.duplocloud.net --admin --interactive
      ```

    Example: Get AWS Environment Variables  
      Here is an example using a query and env output to create some just in time aws credentials. 

      ```sh
      duploctl jit aws -o env -q '{AWS_ACCESS_KEY_ID: AccessKeyId, AWS_SECRET_ACCESS_KEY: SecretAccessKey, AWS_SESSION_TOKEN: SessionToken, AWS_REGION: Region}'
      ```

      A one liner to export those credentials as environment variables. 
      ```sh
      for i in `duploctl jit aws -q '{AWS_ACCESS_KEY_ID: AccessKeyId, AWS_SECRET_ACCESS_KEY: SecretAccessKey, AWS_SESSION_TOKEN: SessionToken, AWS_REGION: Region}' -o env`; do export $i; done
      ```

    Args:
      nocache (bool): Do not use cached credentials. Only for other methods to use.

    Returns:
      sts (dict): The AWS STS session credentials. 
    """
    sts = None
    path = None
    k = self.duplo.cache_key_for("aws-creds")
    nc = nocache if nocache is not None else self.duplo.nocache

    # check if admin or choose tenant
    if self.duplo.isadmin:
      path = "adminproxy/GetJITAwsConsoleAccessUrl"
    else:
      t = self.duplo.load("tenant")
      tenant = t.find()
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
      if "Expiration" not in sts:
        sts["Expiration"] = self.duplo.expiration()
      self.duplo.set_cached_item(k, sts)
    sts["Version"] = 1
    return sts

  @Command()
  def k8s(self,
          planId: args.PLAN = None):
    """Kubernetes JIT Exec Credentials
    
    Provides a full exec credential for kubectl. The default return is a valid exec credential for the kubectl CLI. The global `--admin` flag can be used to get the credentials for an admin, or else per tenant. 
    An admin can pass the `--plan` or else it will be discovered from the chosen tenant. A non admin must 
    choose a tenant. 

    Usage:  
      ```sh
      duploctl jit k8s
      ```

    Args:
      planId: The planId aka name the infrastructure.
    """
    # either plan or tenant in cache key
    pt = planId or self.duplo.tenant or self.duplo.tenantid
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
      if self.duplo.tenantid:
        ctx["Name"] = self.duplo.tenantid
        ctx["cmd_arg"] = "--tenant-id"
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
      planId: The planId of the infrastructure.
    
    Returns:
      dict: The k8s context.
    """
    tenant = None
    tenant_id = self.duplo.tenantid
    tenant_name = self.duplo.tenant
    identified = True if tenant_id or tenant_name else False
    admin = self.duplo.isadmin

    # don't even like try sometimes
    if not admin and not identified:
      raise DuploError("--tenant is required", 300)
    if not planId and not identified:
      raise DuploError("--plan or --tenant is required", 300)
    
    # and admin needs a plan and may have a identified a tenant
    # or maybe it's not an admin and a name was used to identify the tenant
    if (admin and not planId) or (not admin and not tenant_id):
      tenant_svc = self.duplo.load("tenant")
      tenant = tenant_svc.find(tenant_name)
      planId = tenant.get("PlanID")
      tenant_id = tenant.get("TenantId")

    # choose the correct path
    path = (f"v3/admin/plans/{planId}/k8sConfig"
            if admin
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

    t = jwt.decode(jwt=ctx["Token"],algorithms=["HS256"],options={"verify_signature": False})
    exp = datetime.fromtimestamp(t["exp"]).strftime('%Y-%m-%dT%H:%M:%S+00:00')

    return {
      "kind": "ExecCredential",
      "apiVersion": "client.authentication.k8s.io/v1beta1",
      "spec": {
        "cluster": cluster,
        "interactive": False
      },
      "status": {
        "token": ctx["Token"],
        "expirationTimestamp": exp
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
  

    
