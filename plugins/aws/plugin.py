import glob
import os
import time
from duplocloud.client import DuploClient
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResource
from duplocloud.commander import Resource, Command
import duplocloud.args as args
import boto3
from multiprocessing.pool import ThreadPool 

@Resource("aws")
class DuploAWS(DuploResource):
  
  def __init__(self, duplo: DuploClient):
    super().__init__(duplo)
    self.__creds = None
    self.__region = None
    self.__tenant_svc = duplo.load("tenant")

  # def __call__(self, *args):
  #   return {
  #     "message": "Hello from AWS plugin dude!"
  #   }
  
  def client(self, 
             name: str, 
             region: str = None, 
             refresh: bool = False):
    if not self.__creds or refresh:
      jit_svc = self.duplo.load("jit")
      self.__creds = jit_svc.aws()
      # if admin then we need the correct region from the tenant
      if self.duplo.tenant and self.duplo.isadmin:
        r = self.__tenant_svc.region()
        self.__creds["Region"] = r["region"]
    c = self.__creds
    return boto3.client(
        name,
        aws_access_key_id=c.get('AccessKeyId'),
        aws_secret_access_key=c.get('SecretAccessKey'),
        aws_session_token=c.get('SessionToken'),
        region_name=region or c.get('Region')
    )
  
  @Command()
  def update_website(self, 
                     name: args.NAME,
                     dir: args.CONTENT_DIR="dist",
                     wait: args.WAIT=False):
    """Update website
    
    Updates a static website hosted on S3 bucket and served via CloudFront. 
    First the contents of the bucket are updated and then the CloudFront cache is invalidated.

    """
    # make sure the dir directory exists
    if not os.path.exists(dir):
      raise DuploError(f"Directory '{dir}' does not exist.", 404)

    # get the needed clients
    s3 = self.client("s3")
    cdf = self.client("cloudfront")

    # scope into tenant
    tenant = self.__tenant_svc.find()
    tenant_name = tenant["AccountName"]

    # find the distribution
    distributions = cdf.list_distributions()
    comment = f"duploservices-{tenant_name}-{name}"
    dist = next((
      d for d in distributions["DistributionList"]["Items"] 
      if d["Comment"] == comment
    ), None)
    if not dist:
      raise DuploError(f"CloudFront distribution '{comment}' not found.", 404)
    dist_id = dist["Id"]

    # find the bucket name from the distribution
    s3_domain = next((
      o["DomainName"] for o in dist["Origins"]["Items"] 
      if o["Id"] == dist["DefaultCacheBehavior"]["TargetOriginId"]
    ), None)
    bucket_name = s3_domain.split(".")[0]
    
    # get current list of objects in the bucket
    live_objs = s3.list_objects_v2(Bucket=bucket_name)
    live_files = [o["Key"] for o in live_objs.get("Contents", [])]

    # get flat list of files in dir
    tree = glob.glob('**/*', root_dir=dir,recursive=True, include_hidden=True)
    files = []
    # add a trailing slash to each directory because s3 folders have a slash :/
    for n, p in enumerate(tree):
      if os.path.isdir(f"{dir}/{p}"):
        tree[n] = f"{p}/"
      else: # collect the files
        files.append(p)

    # delete objects not in the local tree
    del_objs = [{"Key": o} for o in list(set(live_files) - set(tree))]
    if del_objs:
      s3.delete_objects(Bucket=bucket_name, Delete={"Objects": del_objs})
      for o in del_objs:
        self.duplo.logger.info(f"Deleted {o['Key']}")

    # upload the contents of the dir to the bucket
    pool = ThreadPool(10)
    pool.map(
      lambda key: s3.upload_file(
        Filename=f"{dir}/{key}", 
        Bucket=bucket_name, 
        Key=key,
        Callback=lambda x: self.duplo.logger.info(f"Uploading {x}B to {key}")
      ), 
      files
    )

    # invalidate the CloudFront cache
    call_ref = str(time.time()).replace(".", "")
    inv = cdf.create_invalidation(
      DistributionId=dist_id,
      InvalidationBatch={
        "Paths": {
          "Quantity": 1,
          "Items": ["/*"]
        },
        "CallerReference": call_ref
      }
    )

    # now wait for the invalidation to complete
    if wait:
      waiter = cdf.get_waiter('invalidation_completed')
      waiter.config.delay = 10
      waiter.config.max_attempts = 60
      waiter.wait(
        DistributionId=dist_id, 
        Id=inv['Invalidation']['Id']
      )
      self.duplo.logger.info(f"Invalidation by {call_ref} completed.")

    return {
      "message": f"Updated website '{name}'",
      "distribution": dist_id,
      "bucket": bucket_name,
      "pruned": len(del_objs),
      "uploaded": len(files)
    }

