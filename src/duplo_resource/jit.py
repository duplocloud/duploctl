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

INSTALL_HINT = """
Install duploctl for use with kubectl by following
https://cli.duplocloud.com/Jit/
"""

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
  def token(self) -> dict:
    """Get JWT Token
    
    Get the JWT token for the current user. This is the token that is used to authenticate with the Duplo API. 

    Usage:  
      ```sh
      duploctl jit token
      ```

    Returns:
      token: The JWT token.
    """
    return {"token": self.duplo.token}
  
  @Command()
  def gcp(self, nocache: bool = None) -> dict:
    """GCP Access Token
    
    Get the GCP JWT token for the current user. This is the token that is used to authenticate with the GCP API. You must be an admin to use this feature.  

    Example: Using for gcloud cli access
      Here is how to set the needed environment variables for the gcloud cli.

      ```sh
      for i in $(duploctl jit gcp -q '{CLOUDSDK_AUTH_ACCESS_TOKEN: Token, CLOUDSDK_CORE_PROJECT: ProjectId}' -o env); do export $i; done
      ```

    Usage:  
      ```sh
      duploctl jit gcp
      ```

    Returns:
      token: The GCP JWT token.
    """
    k = self.duplo.cache_key_for("gcp-creds")
    nc = nocache if nocache is not None else self.duplo.nocache
    t = self.duplo.load("tenant")
    tenant = t.find()
    path = f"v3/admin/google/{tenant['TenantId']}/apiToken"
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
    return sts

  @Command()
  def aws(self, nocache: bool = None) -> dict:
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
      sts: The AWS STS session credentials. 
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
  def update_aws_config(self,
                        name: args.NAME) -> dict:
    """Update AWS Config
    
    Update the AWS config file with a new profile. This will add a new profile to the AWS config file.
    This will honor the `AWS_CONFIG_FILE` environment variable if it is set. 
    This will set the aws cli credentialprocess to use the `duploctl jit aws` command. 
    The generated command will inherit the `--host`, `--admin`, and `--interactive` flags from the current command.

    Usage:
      ```sh
      duploctl jit update_aws_config myprofile
      ```

    Example: Add Admin Profile
      Run this command to add an admin profile.
      ```sh
      duploctl jit update_aws_config myportal --admin --interactive
      ```
      This generates the following in the AWS config file.
      ```toml
      [profile myportal]
      region = us-west-2
      credential_process = duploctl jit aws --host https://myportal.duplocloud.net --interactive --admin
      ```

    Args:
      name: The name of the profile to add.
    
    Returns:
      msg: The message that the profile was added.
    """
    config = os.environ.get("AWS_CONFIG_FILE", f"{Path.home()}/.aws/config")
    cp = configparser.ConfigParser()
    cp.read(config)

    # If name is not provided, set default profile name to "duplo"
    name = name or "duplo"

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
  def web(self) -> dict:
    """Open Cloud Console

    Opens a default or specified browser to the Duploclouds underlying cloud. 
    Currently this only supports AWS. The global `--browser` flag can be used to specify a browser.

    Usage:  

    ```sh
    duploctl jit web --browser chrome
    ```
    
    Returns:
      msg: The message that the browser is opening.
    """
    b = self.duplo.browser
    wb = webbrowser if not b else webbrowser.get(b)
    sts = self.aws(nocache=True)
    wb.open(sts["ConsoleUrl"], new=0, autoraise=True)
    return {
      "message": "Opening AWS console in browser"
    }

  @Command()
  def k8s(self,
          planId: args.PLAN = None) -> dict:
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

    Returns:
      credentials: A Kubernetes client [ExecCredential](https://kubernetes.io/docs/reference/config-api/client-authentication.v1beta1/).
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
                        name: args.NAME = None,
                        planId: args.PLAN = None,
                        save: bool = True) -> dict:
    """Update Kubeconfig
    
    Update the kubeconfig file with a new context. This will add a new context to the kubeconfig file. This will honor the `KUBECONFIG` environment variable if it is set. The generated command will inherit the `--host`, `--admin`, and `--interactive` flags from the current command. 

    Usage:
      ```sh
      duploctl jit update_kubeconfig --plan myplan
      ```

    Example: Add Admin Context
      Run this command to add an admin context.
      ```sh
      duploctl jit update_kubeconfig --plan myplan --admin --interactive
      ```
      This generates the following user credential process in the kubeconfig file.
      ```yaml
      users:
      - name: myplan
        user:
          exec:
            apiVersion: client.authentication.k8s.io/v1beta1
            args:
            - jit
            - k8s
            - --plan
            - myplan
            - --host
            - https://myportal.duplocloud.net
            - --admin
            - --interactive
            command: duploctl
            env: null
            installHint: |2

              Install duploctl for use with kubectl by following
              https://github.com/duplocloud/duploctl
            interactiveMode: IfAvailable
            provideClusterInfo: false
      ```

    Args:
      planId: The planId of the infrastructure.
      save: Save the kubeconfig file. This is a code only option. 
    
    Returns:
      msg: The message that the kubeconfig was updated. Unless save is False, then the kubeconfig is returned.
    """
    # first get the kubeconfig file and parse it
    kubeconfig_path = os.environ.get("KUBECONFIG", f"{Path.home()}/.kube/config")
    kubeconfig = (yaml.safe_load(open(kubeconfig_path, "r")) 
                  if os.path.exists(kubeconfig_path) 
                  else self.__empty_kubeconfig())
    # load the cluster config info
    ctx = self.k8s_context(planId)
    ctx["PlanID"] = planId or ctx["Name"].removeprefix("duploinfra-")
    ctx["ARGS"] = ["jit", "k8s"]
    if self.duplo.isadmin:
      ctx["Name"] = name or ctx["PlanID"]
      ctx["ARGS"].extend(["--plan", ctx["PlanID"]])
      if self.duplo.tenant:
        ctx["DefaultNamespace"] = f"duploservices-{self.duplo.tenant}"
    else:
      ctx["Name"] = name or self.duplo.tenantid or self.duplo.tenant
    # add the cluster, user, and context to the kubeconfig
    self.__add_to_kubeconfig("clusters", self.__cluster_config(ctx), kubeconfig)
    self.__add_to_kubeconfig("users", self.__user_config(ctx), kubeconfig)
    self.__add_to_kubeconfig("contexts", self.__context_config(ctx), kubeconfig)
    kubeconfig["current-context"] = ctx["Name"]
    if save:
      # write the kubeconfig back to the file
      with open(kubeconfig_path, "w") as f:
        yaml.safe_dump(kubeconfig, f)
      return {"message": f"kubeconfig updated successfully to {kubeconfig_path}"}
    else:
      return kubeconfig
  
  @Command()
  def k8s_context(self, 
                  planId: args.PLAN = None) -> dict:
    """Get k8s context
    
    Gets context based on planId or tenant name or admin or nonadmin. 

    Args:
      planId: The planId of the infrastructure.
    
    Returns:
      context: The k8s context.
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

    # only add the ca if it is present, Azure won't have one
    if (ca := ctx.get("CertificateAuthorityDataBase64", None)):
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
    if (ca := ctx.get("CertificateAuthorityDataBase64", None)):
      cluster["certificate-authority-data"] = ca
    else:
      cluster["insecure-skip-tls-verify"] = True
    return {
      "name": ctx["PlanID"],
      "cluster": cluster
    }
  
  def __user_config(self, ctx):
    """Build a kubeconfig user object"""
    cmd = self.duplo.build_command(*ctx["ARGS"])
    return {
      "name": ctx["Name"],
      "user": {
        "exec": {
          "apiVersion": "client.authentication.k8s.io/v1beta1",
          "installHint": INSTALL_HINT,
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
        "cluster": ctx["PlanID"],
        "user": ctx["Name"],
        "namespace": ctx["DefaultNamespace"]
      }
    }
  
  def __add_to_kubeconfig(self, section, item, kubeconfig):
    """Add an item to a kubeconfig section if it is not already present"""
    exists = False
    for i in kubeconfig[section]:
      if i["name"] == item["name"]:
        exists = True
        i.update(item)
        break
    if not exists:
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
  

    
