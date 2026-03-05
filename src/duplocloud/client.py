import requests
from cachetools import cachedmethod, TTLCache
from duplocloud.commander import Client
from duplocloud.errors import DuploError, DuploExpiredCache, DuploConnectionError
from duplocloud.server import TokenServer

@Client("duplo")
class DuploAPI():
  """Duplo API Client

  HTTP client for the Duplo API. Handles authentication, request caching,
  and response validation.
  """
  def __init__(self, duplo):
    self.duplo = duplo
    self._ttl_cache = TTLCache(maxsize=128, ttl=10)
    self.cache = duplo.load("cache")

  @property
  def token(self) -> str:
    if not self.duplo.host:
      raise DuploError("Host for Duplo portal is required", 500)
    if not self.duplo.token and self.duplo.interactive:
      self.duplo.token = self.interactive_token()
    if not self.duplo.token:
      raise DuploError("Token for Duplo portal is required", 500)
    return self.duplo.token

  def interactive_token(self) -> str:
    t = None
    k = self.cache.key_for("duplo-creds")
    try:
      if self.duplo.nocache:
        t = self.request_token()
      else:
        t = self.cached_token(k)
    except DuploExpiredCache:
      t = self.request_token()
      c = self._token_cache(t)
      self.cache.set(k, c)
    return t

  def cached_token(self, key: str) -> str:
    c = self.cache.get(key)
    if (exp := c.get("Expiration", None)) and (t := c.get("DuploToken", None)):
      if not self.cache.expired(exp):
        return t
    raise DuploExpiredCache(key)

  def request_token(self) -> str:
    isadmin = "true" if self.duplo.isadmin else "false"
    path = "app/user/verify-token"
    with TokenServer(self.duplo.host) as server:
      try:
        page = f"{path}?localAppName=duploctl&localPort={server.server_port}&isAdmin={isadmin}&redirect=true"
        server.open_callback(page, self.duplo.browser)
        return server.serve_token()
      except KeyboardInterrupt:
        server.shutdown()

  def _token_cache(self, token, otp=False) -> dict:
    return {
      "Version": "v1",
      "DuploToken": token,
      "Expiration": self.cache.expiration(),
      "NeedOTP": otp
    }

  def _request(self, method: str, path: str, **kwargs):
    try:
      response = requests.request(
        method,
        url=f"{self.duplo.host}/{path}",
        headers=self._headers(),
        timeout=self.duplo.timeout,
        **kwargs,
      )
    except requests.exceptions.Timeout as e:
      raise DuploConnectionError("Request timed out while connecting to Duplo") from e
    except requests.exceptions.ConnectionError as e:
      raise DuploConnectionError("Failed to establish connection with Duplo") from e
    except requests.exceptions.RequestException as e:
      raise DuploConnectionError("Failed to send request to Duplo") from e
    return self._validate_response(response)

  @cachedmethod(lambda self: self._ttl_cache)
  def get(self, path: str):
    """Get a Duplo resource.

    This request is cached for 60 seconds.

    Args:
      path: The path to the resource.
    Returns:
      The resource as a JSON object.
    """
    return self._request("GET", path)

  def post(self, path: str, data: dict={}):
    """Post data to a Duplo resource.

    Args:
      path: The path to the resource.
      data: The data to post.
    Returns:
      The response as a JSON object.
    """
    return self._request("POST", path, json=data)

  def put(self, path: str, data: dict={}):
    """Put data to a Duplo resource.

    Args:
      path: The path to the resource.
      data: The data to post.
    Returns:
      The response as a JSON object.
    """
    return self._request("PUT", path, json=data)

  def delete(self, path: str):
    """Delete a Duplo resource.

    Args:
      path: The path to the resource.
    Returns:
      The response as a JSON object.
    """
    return self._request("DELETE", path)

  def disable_get_cache(self) -> None:
    """Disable the get cache for this client."""
    self._ttl_cache = None

  def _headers(self) -> dict:
    t = self.token
    return {
      'Content-Type': 'application/json',
      'Authorization': f"Bearer {t}"
    }

  def _validate_response(self, response: requests.Response) -> requests.Response:
    if 200 <= response.status_code < 300:
      return response

    if response.status_code == 404:
      raise DuploError(f"Resource not found: {response.text}", response.status_code)

    if response.status_code == 401:
      raise DuploError(response.text, response.status_code)

    if response.status_code == 403:
      raise DuploError(f"Unauthorized: {response.text}", response.status_code)

    if response.status_code == 400:
      raise DuploError(response.text, response.status_code)

    raise DuploError(f"Duplo responded with ({response.status_code}): {response.text}", response.status_code)
