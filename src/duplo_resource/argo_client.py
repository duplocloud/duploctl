import requests
from cachetools import cachedmethod, TTLCache
from urllib.parse import unquote, quote
from duplocloud.commander import Client
from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploConnectionError


class _NullCache(dict):
  """A cache that never stores anything, effectively disabling caching."""
  def __setitem__(self, key, value):
    pass  # never store


@Client("argo_wf")
class DuploArgoClient():
  """Argo Workflow HTTP Client

  HTTP proxy client for Argo Workflows via the DuploCloud gateway.
  Delegates JWT token acquisition and caching to the jit.argo_wf() command.

  Shared by all Argo resources (argo_wf, argo_wf_template,
  argo_cluster_wf_template, etc.) via @Resource(client="argo_wf").
  """

  def __init__(self, duplo: DuploCtl):
    self.duplo = duplo
    self.jit = duplo.load("jit")
    self._argo_verified = False
    self._ttl_cache = TTLCache(maxsize=128, ttl=10)

  def _ensure_argo_enabled(self):
    """Check that Argo Workflows is enabled on the tenant infrastructure.

    Looks for DuploCiTenant in the infrastructure CustomData. Only runs
    once per client instance.

    Raises:
      DuploError: If Argo Workflows is not enabled.
    """
    if self._argo_verified:
      return
    tenant = self.duplo.load("tenant").find()
    plan_id = tenant.get("PlanID")
    if not plan_id:
      raise DuploError("Tenant has no associated infrastructure plan", 400)
    infra = self.duplo.load("infrastructure").find(plan_id)
    custom_data = infra.get("CustomData", []) or []
    ci_tenant = next(
      (item.get("Value") for item in custom_data
       if item.get("Key") == "DuploCiTenant"),
      None,
    )
    if not ci_tenant:
      raise DuploError(
        "Argo Workflows is not enabled for this infrastructure. "
        "Please contact your administrator.",
        400,
      )
    self._argo_verified = True

  def _get_auth(self) -> dict:
    """Get Argo auth data (Token and TenantId) via jit."""
    self._ensure_argo_enabled()
    return self.jit.argo_wf()

  def _headers(self, auth: dict) -> dict:
    return {
      "Content-Type": "application/json",
      "Authorization": f"Bearer {auth['Token']}",
      "duplotoken": self.duplo.token,
    }

  def _full_path(self, api_path: str, tenant_id: str, auth: dict) -> str:
    argo_tenant_id = auth["TenantId"]
    return (
      f"argo-wf/{argo_tenant_id}/api/v1/{api_path}"
      f"?current_tenant_id={tenant_id}"
    )

  def _request(self, method: str, api_path: str, tenant_id: str, **kwargs):
    auth = self._get_auth()
    url = f"{self.duplo.host}/{self._full_path(api_path, tenant_id, auth)}"
    try:
      response = requests.request(
        method,
        url=url,
        headers=self._headers(auth),
        timeout=self.duplo.timeout,
        **kwargs,
      )
    except requests.exceptions.Timeout as e:
      raise DuploConnectionError("Argo request timed out") from e
    except requests.exceptions.ConnectionError as e:
      raise DuploConnectionError("Failed to connect to Argo") from e
    except requests.exceptions.RequestException as e:
      raise DuploConnectionError("Argo request failed") from e
    return self._validate_response(response)

  @cachedmethod(lambda self: self._ttl_cache)
  def _get_cached(self, api_path: str, tenant_id: str):
    return self._request("GET", api_path, tenant_id)

  def get(self, api_path: str, tenant_id: str, **kwargs):
    """GET request to the Argo proxy.

    Simple GETs (no extra kwargs) are cached for 10 seconds. Requests
    with streaming or query params bypass the cache to avoid
    unhashable-key errors and stale streaming responses.

    Args:
      api_path: Argo API path relative to /api/v1/.
      tenant_id: Current tenant ID for the proxy query param.
      **kwargs: Extra kwargs forwarded to requests.request (e.g. stream,
        params).

    Returns:
      The HTTP response object.
    """
    if kwargs:
      return self._request("GET", api_path, tenant_id, **kwargs)
    return self._get_cached(api_path, tenant_id)

  def disable_get_cache(self) -> None:
    """Disable the GET cache for this client."""
    self._ttl_cache = _NullCache()

  def post(self, api_path: str, tenant_id: str, data: dict = {}):
    """POST request to the Argo proxy.

    Args:
      api_path: Argo API path relative to /api/v1/.
      tenant_id: Current tenant ID for the proxy query param.
      data: JSON body to send.

    Returns:
      The HTTP response object.
    """
    return self._request("POST", api_path, tenant_id, json=data)

  def put(self, api_path: str, tenant_id: str, data: dict = {}):
    """PUT request to the Argo proxy.

    Args:
      api_path: Argo API path relative to /api/v1/.
      tenant_id: Current tenant ID for the proxy query param.
      data: JSON body to send.

    Returns:
      The HTTP response object.
    """
    return self._request("PUT", api_path, tenant_id, json=data)

  def delete(self, api_path: str, tenant_id: str):
    """DELETE request to the Argo proxy.

    Args:
      api_path: Argo API path relative to /api/v1/.
      tenant_id: Current tenant ID for the proxy query param.

    Returns:
      The HTTP response object.
    """
    return self._request("DELETE", api_path, tenant_id)

  def sanitize_path_segment(self, segment: str) -> str:
    """Sanitize a path segment to prevent path traversal attacks.

    Checks both raw and URL-decoded forms for path separators and
    traversal patterns, then returns a URL-encoded segment.

    Args:
      segment: The path segment to sanitize.

    Returns:
      The URL-encoded sanitized segment.

    Raises:
      DuploError: If the segment contains path traversal patterns.
    """
    if not segment:
      return segment
    raw = str(segment)
    decoded = unquote(raw)

    def _invalid(s: str) -> bool:
      return (
        s.startswith("/") or
        ".." in s or
        "/" in s or
        "\\" in s
      )

    if _invalid(raw) or _invalid(decoded):
      raise DuploError(f"Invalid path segment: {segment}", 400)
    return quote(raw, safe="")

  def _validate_response(
    self, response: requests.Response
  ) -> requests.Response:
    if 200 <= response.status_code < 300:
      return response
    if response.status_code == 404:
      raise DuploError(
        f"Argo resource not found: {response.text}", 404
      )
    if response.status_code == 401:
      raise DuploError(response.text, 401)
    if response.status_code == 403:
      raise DuploError(
        f"Argo unauthorized: {response.text}", 403
      )
    if response.status_code == 400:
      raise DuploError(response.text, 400)
    raise DuploError(
      f"Argo responded with ({response.status_code}): {response.text}",
      response.status_code,
    )
