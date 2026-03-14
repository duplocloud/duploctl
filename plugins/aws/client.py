"""DuploCloud AWS client extension point.

Provides JIT-authenticated boto3 client creation via the
@Client("aws") extension point, injectable into any @Resource
via @Resource(..., client="aws").

Usage in a resource:
    @Resource("myresource", client="aws")
    class MyResource(DuploResource):
        def __init__(self, duplo):
            super().__init__(duplo)
            # self.client is DuploAWSClient (injected after __init__)

        @property
        def s3(self):
            return self.client.load("s3")
"""

import boto3

from duplocloud.commander import Client
from duplocloud.controller import DuploCtl


@Client("aws")
class DuploAWSClient:
    """AWS boto3 client factory authenticated via DuploCloud JIT.

    Acquired via duplo.load_client("aws"). Caches STS credentials
    and exposes load(service_name) to create configured boto3
    clients. Injected automatically into any
    @Resource(client="aws") via the _inject_client mechanism.
    """

    def __init__(self, duplo: DuploCtl):
        self.duplo = duplo
        self.__creds = None

    def load(
        self,
        name: str,
        region: str = None,
        refresh: bool = False,
    ):
        """Create a boto3 client authenticated via DuploCloud JIT.

        Fetches and caches STS credentials through the JIT service.
        Credentials are refreshed on the first call or when
        refresh=True.

        Args:
          name: boto3 service name (e.g. 'cloudformation', 's3').
          region: Override the region from JIT credentials.
          refresh: Force credential refresh.

        Returns:
          A configured boto3 client instance.
        """
        if not self.__creds or refresh:
            jit_svc = self.duplo.load("jit")
            self.__creds = jit_svc.aws()
            if self.duplo.tenant and getattr(
                self.duplo, "isadmin", False
            ):
                tenant_svc = self.duplo.load("tenant")
                r = tenant_svc.region()
                self.__creds["Region"] = r["region"]
        c = self.__creds
        return boto3.client(
            name,
            aws_access_key_id=c.get("AccessKeyId"),
            aws_secret_access_key=c.get("SecretAccessKey"),
            aws_session_token=c.get("SessionToken"),
            region_name=region or c.get("Region"),
        )
