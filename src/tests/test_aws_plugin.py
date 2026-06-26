"""Unit tests for the duploctl-aws plugin.

Tests cover:
  - DuploAWSClient (@Client injection, cred caching, refresh)
  - DuploAWS.load() delegation to injected client
  - DuploAWS.update_website() logic (file sync, deletion, invalidation)
  - Entry point registration (both duplocloud.net and clients.duplocloud.net)
"""

import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_duplo(tenant="default", isadmin=False):
    """Return a minimal DuploCtl-like mock."""
    duplo = MagicMock()
    duplo.tenant = tenant
    duplo.isadmin = isadmin
    duplo.host = "https://test.duplocloud.net"
    duplo.token = "test-token"
    return duplo


def _make_aws_client(duplo=None, creds=None):
    """Instantiate DuploAWSClient with a mock duplo and optional creds preset."""
    from duploctl_aws.client import DuploAWSClient
    client = DuploAWSClient(duplo or _make_duplo())
    if creds:
        # bypass the private name-mangled attribute
        client._DuploAWSClient__creds = creds
    return client


# ---------------------------------------------------------------------------
# DuploAWSClient — unit tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDuploAWSClient:

    def test_client_decorator_registers_kind(self):
        """@Client("aws") sets .kind = "aws" on the class."""
        from duploctl_aws.client import DuploAWSClient
        assert DuploAWSClient.kind == "aws"

    def test_first_load_fetches_jit_creds(self):
        """load() calls jit.aws() on first invocation."""
        duplo = _make_duplo()
        creds = {
            "AccessKeyId": "AKIA...",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Region": "us-east-1",
        }
        jit_mock = MagicMock()
        jit_mock.aws.return_value = creds
        duplo.load.return_value = jit_mock

        with patch("boto3.client") as boto_mock:
            boto_mock.return_value = MagicMock()
            client = _make_aws_client(duplo)
            client.load("s3")

        duplo.load.assert_called_once_with("jit")
        jit_mock.aws.assert_called_once()

    def test_second_load_uses_cached_creds(self):
        """load() reuses cached creds on subsequent calls."""
        creds = {
            "AccessKeyId": "AKIA...",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Region": "us-east-1",
        }
        client = _make_aws_client(creds=creds)

        with patch("boto3.client") as boto_mock:
            boto_mock.return_value = MagicMock()
            client.load("s3")
            client.load("cloudformation")

        # boto3.client called twice but jit was never touched (no duplo.load)
        assert boto_mock.call_count == 2
        client.duplo.load.assert_not_called()

    def test_refresh_forces_new_creds(self):
        """load(refresh=True) always calls jit.aws() again."""
        duplo = _make_duplo()
        creds = {
            "AccessKeyId": "AKIA...",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Region": "us-east-1",
        }
        jit_mock = MagicMock()
        jit_mock.aws.return_value = creds
        duplo.load.return_value = jit_mock

        with patch("boto3.client") as boto_mock:
            boto_mock.return_value = MagicMock()
            client = _make_aws_client(duplo, creds=creds)
            # already has creds but refresh=True
            client.load("s3", refresh=True)

        jit_mock.aws.assert_called_once()

    def test_region_override_passed_to_boto(self):
        """Explicit region overrides the JIT region."""
        creds = {
            "AccessKeyId": "AKIA...",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Region": "us-east-1",
        }
        client = _make_aws_client(creds=creds)

        with patch("boto3.client") as boto_mock:
            boto_mock.return_value = MagicMock()
            client.load("lambda", region="eu-west-1")

        _, kwargs = boto_mock.call_args
        assert kwargs["region_name"] == "eu-west-1"

    def test_admin_with_tenant_fetches_region(self):
        """Admin + tenant set → tenant.region() used to override Region."""
        duplo = _make_duplo(tenant="dev", isadmin=True)
        creds = {
            "AccessKeyId": "AKIA...",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Region": "us-east-1",
        }
        jit_mock = MagicMock()
        jit_mock.aws.return_value = creds

        tenant_mock = MagicMock()
        tenant_mock.region.return_value = {"region": "ap-southeast-2"}

        def _load_side_effect(name):
            if name == "jit":
                return jit_mock
            if name == "tenant":
                return tenant_mock
            return MagicMock()

        duplo.load.side_effect = _load_side_effect

        with patch("boto3.client") as boto_mock:
            boto_mock.return_value = MagicMock()
            client = _make_aws_client(duplo)
            client.load("s3")

        _, kwargs = boto_mock.call_args
        assert kwargs["region_name"] == "ap-southeast-2"

    def test_boto_called_with_correct_credentials(self):
        """boto3.client receives the JIT key/secret/token."""
        creds = {
            "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
            "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG",
            "SessionToken": "AQoXnyc4lcK4w4",
            "Region": "us-west-2",
        }
        client = _make_aws_client(creds=creds)

        with patch("boto3.client") as boto_mock:
            boto_mock.return_value = MagicMock()
            client.load("sts")

        boto_mock.assert_called_once_with(
            "sts",
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG",
            aws_session_token="AQoXnyc4lcK4w4",
            region_name="us-west-2",
        )


# ---------------------------------------------------------------------------
# DuploAWS resource — unit tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDuploAWSResource:

    def _make_plugin(self):
        """Return a DuploAWS instance with a mocked injected client."""
        from duploctl_aws.plugin import DuploAWS
        duplo = _make_duplo()
        duplo.load.return_value = MagicMock()  # tenant_svc
        plugin = DuploAWS.__new__(DuploAWS)
        plugin.duplo = duplo
        plugin.client = MagicMock()  # injected DuploAWSClient
        plugin._DuploAWS__tenant_svc = duplo.load.return_value
        return plugin

    def test_load_delegates_to_client(self):
        """DuploAWS.load() calls self.client.load() with the same args."""
        plugin = self._make_plugin()
        fake_boto = MagicMock()
        plugin.client.load.return_value = fake_boto

        result = plugin.load("cloudformation", region="us-west-2", refresh=True)

        plugin.client.load.assert_called_once_with(
            "cloudformation", "us-west-2", True
        )
        assert result is fake_boto

    def test_resource_kind_is_aws(self):
        """DuploAWS.kind is set to 'aws' by the @Resource decorator."""
        from duploctl_aws.plugin import DuploAWS
        assert DuploAWS.kind == "aws"


# ---------------------------------------------------------------------------
# update_website — unit tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestUpdateWebsite:

    def _setup(self, tmp_path):
        """Set up a DuploAWS plugin with all boto mocks and a real tmp dir."""
        from duploctl_aws.plugin import DuploAWS

        duplo = _make_duplo(tenant="myapp")
        tenant_mock = MagicMock()
        tenant_mock.find.return_value = {"AccountName": "myapp"}
        duplo.load.return_value = tenant_mock

        plugin = DuploAWS.__new__(DuploAWS)
        plugin.duplo = duplo
        plugin._DuploAWS__tenant_svc = tenant_mock

        # Create a minimal content dir
        (tmp_path / "index.html").write_text("<html/>")
        (tmp_path / "app.js").write_text("console.log('hi')")

        # Mock injected client
        s3_mock = MagicMock()
        s3_mock.list_objects_v2.return_value = {"Contents": []}
        s3_mock.upload_file.return_value = None
        s3_mock.delete_objects.return_value = {}

        cdf_mock = MagicMock()
        cdf_mock.list_distributions.return_value = {
            "DistributionList": {
                "Items": [{
                    "Comment": "duploservices-myapp-mysite",
                    "Id": "DIST123",
                    "Origins": {
                        "Items": [{
                            "DomainName": "mybucket.s3.amazonaws.com",
                            "Id": "myOrigin",
                        }]
                    },
                    "DefaultCacheBehavior": {
                        "TargetOriginId": "myOrigin",
                    },
                }]
            }
        }
        invalidation_mock = {"Invalidation": {"Id": "INV1"}}
        cdf_mock.create_invalidation.return_value = invalidation_mock

        aws_client_mock = MagicMock()
        aws_client_mock.load.side_effect = lambda name, *a, **kw: (
            s3_mock if name == "s3" else cdf_mock
        )
        plugin.client = aws_client_mock

        return plugin, s3_mock, cdf_mock, tmp_path

    def test_missing_dir_raises(self, tmp_path):
        """DuploError raised when content dir does not exist."""
        from duploctl_aws.plugin import DuploAWS
        from duplocloud.errors import DuploError
        plugin = DuploAWS.__new__(DuploAWS)
        plugin.duplo = MagicMock()
        plugin.client = MagicMock()
        plugin._DuploAWS__tenant_svc = MagicMock()
        with pytest.raises(DuploError, match="does not exist"):
            plugin.update_website("mysite", dir=str(tmp_path / "nonexistent"))

    def test_missing_distribution_raises(self, tmp_path):
        """DuploError raised when no matching CloudFront distribution found."""
        from duploctl_aws.plugin import DuploAWS
        from duplocloud.errors import DuploError
        plugin, s3_mock, cdf_mock, content = self._setup(tmp_path)
        cdf_mock.list_distributions.return_value = {
            "DistributionList": {"Items": []}
        }
        with pytest.raises(DuploError, match="not found"):
            plugin.update_website("mysite", dir=str(content))

    def test_uploads_files(self, tmp_path):
        """All files in the content dir are uploaded to S3."""
        plugin, s3_mock, cdf_mock, content = self._setup(tmp_path)
        result = plugin.update_website("mysite", dir=str(content))
        assert s3_mock.upload_file.call_count == 2
        assert result["uploaded"] == 2

    def test_deletes_stale_objects(self, tmp_path):
        """Objects in S3 but not in local dir are deleted."""
        plugin, s3_mock, cdf_mock, content = self._setup(tmp_path)
        s3_mock.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "index.html"},
                {"Key": "old_file.js"},  # not in local dir
            ]
        }
        result = plugin.update_website("mysite", dir=str(content))
        s3_mock.delete_objects.assert_called_once()
        delete_keys = s3_mock.delete_objects.call_args[1]["Delete"]["Objects"]
        assert any(d["Key"] == "old_file.js" for d in delete_keys)
        assert result["pruned"] == 1

    def test_invalidation_created(self, tmp_path):
        """A CloudFront cache invalidation is always created."""
        plugin, s3_mock, cdf_mock, content = self._setup(tmp_path)
        plugin.update_website("mysite", dir=str(content))
        cdf_mock.create_invalidation.assert_called_once()
        inv_args = cdf_mock.create_invalidation.call_args[1]
        assert inv_args["DistributionId"] == "DIST123"
        assert "/*" in inv_args["InvalidationBatch"]["Paths"]["Items"]

    def test_returns_expected_keys(self, tmp_path):
        """Return dict contains message, distribution, bucket, pruned, uploaded."""
        plugin, s3_mock, cdf_mock, content = self._setup(tmp_path)
        result = plugin.update_website("mysite", dir=str(content))
        assert "message" in result
        assert result["distribution"] == "DIST123"
        assert result["bucket"] == "mybucket"


# ---------------------------------------------------------------------------
# Entry point registration
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_resource_entry_point_registered():
    """duplocloud.net entry point 'aws' loads DuploAWS."""
    from importlib.metadata import entry_points
    eps = entry_points(group="duplocloud.net")
    names = list(eps.names)
    assert "aws" in names


@pytest.mark.unit
def test_client_entry_point_registered():
    """clients.duplocloud.net entry point 'aws' loads DuploAWSClient."""
    from importlib.metadata import entry_points
    eps = entry_points(group="clients.duplocloud.net")
    names = list(eps.names)
    assert "aws" in names
