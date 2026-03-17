import os
from pathlib import Path
import time
from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError
from duplocloud.resource import DuploResource
from duplocloud.commander import Resource, Command
import duplocloud.args as args
from multiprocessing.pool import ThreadPool 

@Resource("aws", client="aws")
class DuploAWS(DuploResource):

  def __init__(self, duplo: DuploCtl):
    super().__init__(duplo)
    self.__tenant_svc = duplo.load("tenant")

  def load(
      self,
      name: str,
      region: str = None,
      refresh: bool = False,
  ):
    """Create a boto3 client authenticated via DuploCloud JIT.

    Delegates to the injected DuploAWSClient so credential
    management is centralised in the @Client("aws") extension.

    Args:
      name: boto3 service name (e.g. 's3', 'cloudfront').
      region: Override the AWS region.
      refresh: Force credential refresh.

    Returns:
      A configured boto3 client.
    """
    return self.client.load(name, region, refresh)
  
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
    s3 = self.client.load("s3")
    cdf = self.client.load("cloudfront")

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

    # get flat list of files in dir (includes hidden files, Python 3.10 compatible)
    tree = [str(p.relative_to(dir)) for p in Path(dir).rglob('*')]
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

