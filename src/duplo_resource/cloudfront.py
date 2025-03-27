import time
import logging
from duplocloud.client import DuploClient
from duplocloud.resource import DuploTenantResourceV3
from duplocloud.errors import DuploError
from duplocloud.commander import Command, Resource
import duplocloud.args as args

# Configure logging
logging.basicConfig(level=logging.INFO)

@Resource("cloudfront")
class CloudFront(DuploTenantResourceV3):

    def __init__(self, duplo: DuploClient):
      super().__init__(duplo, "aws/cloudFrontDistribution")
      self.wait_timeout = 1200

    def wait_check(self, distribution_id):
      """
      Waits for the CloudFront distribution to be in 'Deployed' status.
      """
      start_time = time.time()
      prev_status = None
      max_attempts = self.wait_timeout // 60

      for attempt in range(max_attempts):
        try:
          elapsed_time = time.time() - start_time
          status_response = self.find(distribution_id)
          status = status_response.get("Distribution", {}).get("Status", "Unknown").lower()
          if status != prev_status:
            prev_status = status
          if status == "deployed":
            return status_response
          elif status in ["failed", "error"]:
            raise RuntimeError(f"CloudFront distribution {distribution_id} failed to deploy.")
        except Exception as e:
          logging.error(f"Error checking CloudFront status: {e}")
          raise
        time.sleep(60)
      raise TimeoutError(f"Timed out waiting for CloudFront {distribution_id} to be deployed.")

    @Command()
    def find(self, distribution_id: args.DISTRIBUTION_ID):
      """
      Find a CloudFront distribution by its distribution ID.
      Usage:
        ```sh
        duploctl cloudfront find <distribution_id>
        ```
      Args:
          distribution_id (str): The CloudFront distribution ID.
      Returns:
          dict: The service object.
      """
      try:
        response = self.duplo.get(self.endpoint(name=distribution_id))
        response.raise_for_status()
        return response.json()
      except Exception as e:
        raise DuploError(f"Could not find CloudFront distribution {distribution_id}")

    @Command()
    def create(self, body: args.BODY, wait: args.WAIT = False):
      """
      Create a CloudFront distribution.
      Usage: Basic CLI Use
        ```sh
        duploctl cloudfront create --file cloudfront.yaml
        ```
      Contents of the `cloudfront.yaml` file
        ```yaml
        --8<-- "src/tests/data/cloudfront-create.yaml"
        ```
      Args:
          body: The request payload for CloudFront creation.
          wait: Whether to wait until the distribution is deployed.
      Returns:
          dict: The created distribution details.
      """
      try:
        response = self.duplo.post(self.endpoint(), body)
        response.raise_for_status()
        data = response.json()
        distribution_id = data.get("Id") or data.get("Distribution", {}).get("Id")
        if not distribution_id:
          raise ValueError("Failed to retrieve CloudFront Distribution ID from response.")
        if wait:
          return self.wait_check(distribution_id)
        return data
      except Exception as e:
        raise DuploError(f"Failed to create CloudFront distribution: {e}")

    @Command()
    def update(self, body: args.BODY, wait: args.WAIT=False):
      """
      Update a CloudFront distribution.
      Usage: Basic CLI Use
        ```sh
        duploctl cloudfront update --file cloudfront.yaml
        ```
      Contents of the `cloudfront.yaml` file
        ```yaml
        --8<-- "src/tests/data/cloudfront-update.yaml"
        ```
      Args:
          body: The request payload for CloudFront updation.
          wait: Whether to wait until the distribution is deployed.
      Returns:
          dict: The updated distribution details.
      """
      try:
        response = self.duplo.put(self.endpoint(), body)
        response.raise_for_status()
        data = response.json()
        distribution_id = data.get("Id") or data.get("Distribution", {}).get("Id")
        if not distribution_id:
          raise ValueError("Failed to retrieve CloudFront Distribution ID from response.")
        if wait:
          return self.wait_check(distribution_id)
        return data
      except Exception as e:
        raise DuploError(f"Failed to update CloudFront distribution: {e}")

    @Command()
    def list(self):
      """List CloudFront distributions.
      Usage:
        ```sh
        duploctl cloudfront list
        ```
      Returns:
          list: A list of all cloudfronts.
      """
      response = self.duplo.get(self.endpoint())
      return response.json()

    @Command()
    def disable(self, distribution_id: args.DISTRIBUTION_ID, wait: args.WAIT=False):
      """
      Disable a CloudFront distribution.
      Usage:
          ```sh
          duploctl cloudfront disable <distribution_id>
          ```
      Args:
          distribution_id (str): The ID of the CloudFront distribution to be disabled.
          wait: Whether to wait for the CloudFront distribution to disable.
      Returns:
          dict: The service object.
      """
      body = {"Id":distribution_id,"DistributionConfig":{"Disabled":"true"}}
      response = self.duplo.put(self.endpoint(), body)
      if wait:
        self.wait_check(distribution_id)
      return response.json()
    
    @Command()
    def enable(self, distribution_id: args.DISTRIBUTION_ID, wait: args.WAIT=False):
      """
      Enable a CloudFront distribution.
      Usage:
          ```sh
          duploctl cloudfront enable <distribution_id>
          ```
      Args:
          distribution_id (str): The ID of the CloudFront distribution to be enabled.
          wait: Whether to wait for the CloudFront distribution to enable.
      Returns:
          dict: The service object.
      """
      body = {"Id":distribution_id,"DistributionConfig":{"Enabled":"true"}}
      response = self.duplo.put(self.endpoint(), body)
      if wait:
        self.wait_check(distribution_id)
      return response.json()

    @Command()
    def delete(self, distribution_id: args.DISTRIBUTION_ID):
      """
      Delete a CloudFront distribution.
      Usage:
          ```sh
          duploctl cloudfront delete <distribution_id>
          ```
      Args:
          distribution_id (str): The ID of the CloudFront distribution to delete.
      Returns:
          dict: Confirmation message.
      """
      try:
        response = self.duplo.delete(self.endpoint(distribution_id))
        response.raise_for_status()
        return {"message": f"CloudFront distribution {distribution_id} deleted"}
      except Exception as e:
        raise DuploError(f"Could not delete CloudFront distribution {distribution_id}")

    @Command()
    def get_status(self, distribution_id: args.DISTRIBUTION_ID):
      """
      Retrieve the status of a CloudFront distribution by its distribution ID.
      Usage:
          ```sh
          duploctl cloudfront get_status <distribution_id>
          ```
      Args:
          distribution_id (str): The CloudFront distribution ID.
      Returns:
          str: The status of the CloudFront distribution.
      Raises:
          DuploError: If the CloudFront distribution could not be found or lacks a status.
      """
      try:
        response = self.find(distribution_id)
        status = response.get("Distribution", {}).get("Status")
        if status is None:
            raise DuploError(f"Status not found for CloudFront distribution {distribution_id}")
        return status
      except Exception as e:
        raise DuploError(f"Failed to get status for CloudFront distribution {distribution_id}")
