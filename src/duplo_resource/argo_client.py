import requests
from urllib.parse import unquote, quote
from duplocloud.commander import Client
from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploConnectionError


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

  def _get_auth(self) -> dict:
    """Get Argo auth data (Token and TenantId) via jit."""
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

  def get(self, api_path: str, tenant_id: str, **kwargs):
    """GET request to the Argo proxy.

    Args:
      api_path: Argo API path relative to /api/v1/.
      tenant_id: Current tenant ID for the proxy query param.
      **kwargs: Extra kwargs forwarded to requests.request (e.g. stream,
        params).

    Returns:
      The HTTP response object.
    """
    return self._request("GET", api_path, tenant_id, **kwargs)

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
