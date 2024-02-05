from duplocloud.client import DuploClient
from duplocloud.resource import DuploResource
from duplocloud.commander import Command, Resource
import duplocloud.args as args
from datetime import datetime, timedelta

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
    return self.k8s_exec_credential(creds.json())
  
  def k8s_exec_credential(self, creds):
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
