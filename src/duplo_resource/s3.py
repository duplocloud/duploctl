from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.commander import Resource, Command
import duplocloud.args as args

@Resource("s3")
class DuploS3(DuploTenantResourceV3):
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "aws/s3bucket")

  def name_from_body(self, body):
    return body["Name"]
  
  @Command()
  def readiness_check(self, name: args.NAME):
    """S3 Readiness Check
    
    Check the S3 readiness.

    Usage: Basic CLI Use
      ```bash
      duploctl s3 readiness_check <name>
      ```
    Args:
      name: The name of the s3.
    
    """
    checklist = []
    s3 = self.find(name)
    encryption_type = s3['DefaultEncryption']
    if encryption_type != 'TenantKms':
      encryption_checklist =  {
        "Name": f"{name}",
        "Readiness Check": "Enable Enryption",
        "Status": "Failed",
        "Possible Solution": "Set TenantKms key for encryption",
      }
      checklist.append(encryption_checklist)
    public_access = s3['AllowPublicAccess']
    if public_access:
      public_access_checklist =  {
        "Name": f"{name}",
        "Readiness Check": "Public Access",
        "Status": "Failed",
        "Possible Solution": "Disable AllowPublicAccess",
      }
      checklist.append(public_access_checklist)
    access_log = s3['EnableAccessLogs']
    if access_log is False:
      access_log_checklist =  {
        "Name": f"{name}",
        "Readiness Check": "Access Log",
        "Status": "Failed",
        "Possible Solution": "Enable AccessLogs",
      }
      checklist.append(access_log_checklist)

    return checklist
