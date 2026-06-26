import requests
from cachetools import cachedmethod, TTLCache
from duplocloud.commander import Client
from duplocloud.errors import DuploError, DuploExpiredCache, DuploNotFound, DuploConnectionError
from duplocloud.server import TokenServer
from duplocloud.authcooldown import (
    is_auth_cooldown_enabled, is_tty, check_cooldown_before_listen,
    recover_relay_bind_failure, acquire_or_update_cooldown, clear_auth_cooldown,
    get_host_cache_key, CooldownResult
)


class _NullCache(dict):
    """A cache that never stores anything, effectively disabling caching."""
    def __setitem__(self, key, value):
        pass  # never store

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
    """Request Token from Browser

    Perform an interactive login to the specified host. Opens a temporary web
    browser to the login page and starts a local server to receive the token.
    When the user authorizes the request in the browser, the token is received
    and the server is shutdown.

    If auth cooldown is enabled (via --auth-cooldown flag or DUPLO_AUTH_COOLDOWN
    env var) and the caller is not in a TTY, the cooldown mechanism prevents
    duplicate browser tabs within a configurable window. TTY callers always
    bypass the cooldown.

    Returns:
      The token as a string.
    """
    cooldown_duration, cooldown_enabled = is_auth_cooldown_enabled(self.duplo.auth_cooldown)
    use_cooldown = cooldown_enabled and not is_tty()

    open_browser = True
    listen_port = 0
    timeout = 180  # default 3 minute timeout

    if use_cooldown:
      listen_port, open_browser, timeout, early = check_cooldown_before_listen(
          self.duplo.cache_dir, self.duplo.host, self.duplo.isadmin, 0, cooldown_duration,
          get_cached_token=self._try_cached_token)
      if early is not None:
        return self._handle_cooldown_result(early)
    elif cooldown_enabled:
      self.duplo.logger.info("auth cooldown: TTY detected, bypassing cooldown for %s",
                             get_host_cache_key(self.duplo.host))

    isadmin = "true" if self.duplo.isadmin else "false"
    path = "app/user/verify-token"
    try:
      server = TokenServer(self.duplo.host, timeout=timeout, port=listen_port)
    except OSError:
      if listen_port != 0 and use_cooldown:
        return self._handle_cooldown_result(recover_relay_bind_failure(
            self.duplo.cache_dir, self.duplo.host, self.duplo.isadmin, 0, listen_port, cooldown_duration,
            get_cached_token=self._try_cached_token))
      raise

    with server:
      try:
        if use_cooldown:
          cd_result = acquire_or_update_cooldown(
              self.duplo.cache_dir, self.duplo.host, self.duplo.isadmin, 0, server.server_port,
              open_browser, cooldown_duration,
              get_cached_token=self._try_cached_token)
          if cd_result is not None:
            return self._handle_cooldown_result(cd_result)

        if open_browser:
          page = f"{path}?localAppName=duploctl&localPort={server.server_port}&isAdmin={isadmin}&redirect=true"
          server.open_callback(page, self.duplo.browser)
        else:
          self.duplo.logger.info("auth cooldown: relay — listening on port %d for existing browser tab",
                                 server.server_port)

        token = server.serve_token()

        if use_cooldown:
          clear_auth_cooldown(self.duplo.cache_dir, self.duplo.host, self.duplo.isadmin)

        return token
      except DuploError:
        if use_cooldown:
          clear_auth_cooldown(self.duplo.cache_dir, self.duplo.host, self.duplo.isadmin)
        raise
      except KeyboardInterrupt:
        server.shutdown()

  def _token_cache(self, token, otp=False) -> dict:
    return {
      "Version": "v1",
      "DuploToken": token,
      "Expiration": self.cache.expiration(),
      "NeedOTP": otp
    }

  def _handle_cooldown_result(self, result: CooldownResult):
    """Handle a CooldownResult by raising, returning, or retrying."""
    if result.error:
      raise DuploError(result.error, 403)
    if result.token:
      return result.token
    if result.retry:
      return self.request_token()
    raise DuploError(f"unexpected cooldown result: {result}", 500)

  def _try_cached_token(self) -> str | None:
    """Try Cached Token

    Attempt to read a cached token without raising on expiration.

    Returns:
      The token string, or None if unavailable or expired.
    """
    k = self.cache.key_for("duplo-creds")
    try:
      return self.cached_token(k)
    except (DuploExpiredCache, DuploError, OSError, KeyError):
      return None

  def _request(self, method: str, path: str, extra_headers: dict = None, **kwargs):
    headers = self._headers()
    if extra_headers:
      headers.update(extra_headers)
    try:
      response = requests.request(
        method,
        url=f"{self.duplo.host}/{path}",
        headers=headers,
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

  def post(self, path: str, data: dict={}, headers: dict=None, **kwargs):
    """Post data to a Duplo resource.

    Args:
      path: The path to the resource.
      data: The data to post.
      headers: Optional headers merged over the default auth headers
        (e.g. ``{"Accept": "text/event-stream"}``).
      kwargs: Extra arguments forwarded to the underlying request, such as
        ``stream=True`` for SSE / chunked responses. When streaming, the
        response is returned unbuffered so callers can iterate
        ``iter_lines()`` / ``iter_content()``; use a ``with`` block so the
        connection closes cleanly.
    Returns:
      The response as a JSON object, or a streaming response when
      ``stream=True`` is passed.
    """
    return self._request("POST", path, json=data, extra_headers=headers, **kwargs)

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
    self._ttl_cache = _NullCache()

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
      raise DuploNotFound(response.text)

    if response.status_code == 401:
      raise DuploError(response.text, response.status_code)

    if response.status_code == 403:
      raise DuploError(f"Unauthorized: {response.text}", response.status_code)

    if response.status_code == 400:
      if "not found" in response.text.lower():
        raise DuploNotFound(response.text)
      raise DuploError(response.text, response.status_code)

    raise DuploError(f"Duplo responded with ({response.status_code}): {response.text}", response.status_code)
