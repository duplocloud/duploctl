from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.errors import DuploError, DuploFailedResource, DuploStillWaiting
from duplocloud.commander import Command, Resource
import duplocloud.args as args

@Resource("cloudfront")
class DuploCloudFront(DuploTenantResourceV3):
  """Manage CloudFront Distributions

  Configuring a CloudFront distributions in DuploCloud are content delivery network (CDN) configurations that
  help you improve the performance of your web applications.

  See more details at: https://docs.duplocloud.com/docs/overview/aws-services/cloudfront
  """

  def __init__(self, duplo: DuploClient):
    super().__init__(duplo, "aws/cloudFrontDistribution")

  def wait_check(self, distribution_id):
    status_response = self.find(distribution_id)
    status = status_response.get("Distribution", {}).get("Status", "Unknown").lower()
    if status == "deployed":
      return status_response
    elif status in ["failed", "error"]:
      raise DuploFailedResource(f"CloudFront distribution {distribution_id} failed to deploy.")
    else:
      raise DuploStillWaiting(f"Timed out waiting for CloudFront {distribution_id} to be deployed.")

  @Command()
  def find(self, distribution_id: args.DISTRIBUTION_ID):
    """Find a CloudFront distribution.

    Find a CloudFront distribution by its distribution ID.

    Usage:
      ```sh
      duploctl cloudfront find <distribution_id>
      ```

    Args:
      distribution_id: The CloudFront distribution ID.

    Returns:
      dict: The service object.
    """
    response = self.duplo.get(self.endpoint(name=distribution_id))
    response.raise_for_status()
    return response.json()

  @Command()
  def create(self, body: args.BODY):
    """Create a CloudFront distribution.

    Creates a new CloudFront distribution with the specified configuration.

    Usage: Basic CLI Use
      ```sh
      duploctl cloudfront create -f cloudfront.yaml
      ```

    Example cloudfront.yaml:
      ```yaml
      --8<-- "src/tests/data/cloudfront-create.yaml"
      ```

    Args:
      body: The distribution configuration including origins, behaviors, and other settings.

    Returns:
      dict: The created distribution details including the distribution ID.

    Raises:
      DuploError: If the distribution could not be created or the configuration is invalid.
      DuploFailedResource: If the distribution creation process fails.
    """
    data = None
    try:
      response = self.duplo.post(self.endpoint(), body)
      response.raise_for_status()
      data = response.json()
      distribution_id = data.get("Id") or data.get("Distribution", {}).get("Id")
      if not distribution_id:
        raise ValueError("Failed to retrieve CloudFront Distribution ID from response.")
      if self.duplo.wait:
        self.wait(lambda: self.wait_check(distribution_id) is not None, 1200)
      return data
    except Exception as e:
      raise DuploError(f"Failed to create CloudFront distribution: {e}")

  @Command()
  def update(self, body: args.BODY):
    """Update a CloudFront distribution.

    Updates an existing CloudFront distribution with new configuration settings.

    Usage: Basic CLI Use
      ```sh
      duploctl cloudfront update -f cloudfront.yaml
      ```

    Example cloudfront.yaml:
      ```yaml
      --8<-- "src/tests/data/cloudfront-update.yaml"
      ```

    Args:
      body: The updated distribution configuration.

    Returns:
      dict: The updated distribution details.

    Raises:
      DuploError: If the distribution could not be updated or the configuration is invalid.
      DuploFailedResource: If the update process fails.
    """
    try:
      response = self.duplo.put(self.endpoint(), body)
      response.raise_for_status()
      data = response.json()
      distribution_id = data.get("Id") or data.get("Distribution", {}).get("Id")
      if not distribution_id:
        raise ValueError("Failed to retrieve CloudFront Distribution ID from response.")
      if self.duplo.wait:
        self.wait(lambda: self.wait_check(distribution_id) is not None, 1200)
      return data
    except Exception as e:
      raise DuploError(f"Failed to update CloudFront distribution: {e}")

  @Command()
  def disable(self, distribution_id: args.DISTRIBUTION_ID):
    """Disable a CloudFront distribution.

    Disables content delivery for a CloudFront distribution. When disabled,
    the distribution will stop serving content but will retain its configuration.

    Usage: Basic CLI Use
      ```sh
      duploctl cloudfront disable <distribution-id>
      ```

    Args:
      distribution_id: The ID of the CloudFront distribution to disable.

    Returns:
      dict: The updated distribution details.

    Raises:
      DuploError: If the distribution could not be disabled.
      DuploFailedResource: If the disable process fails.
    """
    body = {"Id":distribution_id,"DistributionConfig":{"Disabled":"true"}}
    response = self.duplo.put(self.endpoint(), body)
    if self.duplo.wait:
      self.wait(lambda: self.wait_check(distribution_id) is not None, 1200)
    return response.json()
  
  @Command()
  def enable(self, distribution_id: args.DISTRIBUTION_ID):
    """Enable a CloudFront distribution.

    Enables content delivery for a previously disabled CloudFront distribution.
    When enabled, the distribution will start serving content using its current
    configuration.

    Usage: Basic CLI Use
      ```sh
      duploctl cloudfront enable <distribution-id>
      ```

    Args:
      distribution_id: The ID of the CloudFront distribution to enable.

    Returns:
      dict: The updated distribution details.

    Raises:
      DuploError: If the distribution could not be enabled.
      DuploFailedResource: If the enable process fails.
    """
    body = {"Id":distribution_id,"DistributionConfig":{"Enabled":"true"}}
    response = self.duplo.put(self.endpoint(), body)
    if self.duplo.wait:
      self.wait(lambda: self.wait_check(distribution_id) is not None, 1200)
    return response.json()

  @Command()
  def delete(self, distribution_id: args.DISTRIBUTION_ID):
    """Delete a CloudFront distribution.

    Permanently removes a CloudFront distribution. This operation is irreversible
    and will remove all distribution settings and cached content. The distribution
    must be disabled before it can be deleted.

    Usage: Basic CLI Use
      ```sh
      duploctl cloudfront delete <distribution-id>
      ```

    Args:
      distribution_id: The ID of the CloudFront distribution to delete.

    Returns:
      dict: Success message confirming the deletion.

    Raises:
      DuploError: If the distribution could not be deleted or is not in a deletable state.
    """
    response = self.duplo.delete(self.endpoint(distribution_id))
    response.raise_for_status()
    return {"message": f"CloudFront distribution {distribution_id} deleted"}

  @Command()
  def get_status(self, distribution_id: args.DISTRIBUTION_ID):
    """Get the current status of a CloudFront distribution.

    Retrieves the current deployment status of a CloudFront distribution.
    The status indicates whether the distribution is deployed, in progress,
    or in an error state.

    Usage: Basic CLI Use
      ```sh
      duploctl cloudfront get-status <distribution-id>
      ```

    Args:
      distribution_id: The ID of the CloudFront distribution to check.

    Returns:
      str: The current status of the distribution (e.g., 'Deployed', 'InProgress').

    Raises:
      DuploError: If the distribution could not be found or the status is unavailable.
    """
    response = self.find(distribution_id)
    status = response.get("Distribution", {}).get("Status")
    if status is None:
      raise DuploError(f"Status not found for CloudFront distribution {distribution_id}")
    return status
