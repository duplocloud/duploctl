import requests
from cachetools import cachedmethod, TTLCache
from duplocloud.client import _NullCache
from duplocloud.commander import Client
from duplocloud.errors import DuploError, DuploNotFound, DuploConnectionError

BASE_PATH = "v1/aiservicedesk"
PAGE_SIZE = 100
"""Server-side page cap on admin data-plane list routes."""


def unwrap_data(response: dict) -> dict:
  """Unwrap a single-object AI HelpDesk envelope.

  Admin data-plane routes wrap payloads as ``{success, data: {...}}``
  while ticket routes return the object bare; bare payloads pass
  through untouched.

  Args:
    response: The decoded JSON response.

  Returns:
    The unwrapped object.
  """
  data = response.get("data")
  return data if isinstance(data, dict) else response


def unwrap_items(response: dict) -> list:
  """Unwrap a list AI HelpDesk envelope.

  Admin data-plane list routes wrap payloads as
  ``{success, data: {items: [...]}}``.

  Args:
    response: The decoded JSON response.

  Returns:
    The list of items, or an empty list when absent.
  """
  data = response.get("data")
  if not isinstance(data, dict):
    return []
  items = data.get("items")
  return items if isinstance(items, list) else []


@Client("helpdesk")
class DuploHelpdeskClient():
  """AI HelpDesk API Client

  HTTP client for the AI HelpDesk (service desk V2) backend. Owns the
  ``v1/aiservicedesk`` URL prefix on the portal host, so resources pass
  paths relative to it, e.g. ``admin/data/workspaces``.

  Auth reuses the portal bearer token; acquisition is delegated to the
  duplo client so interactive login keeps working. Only the token is
  shared — verbs and the GET cache are this client's own, so
  ``disable_get_cache`` never clobbers the shared duplo client's cache.
  """

  def __init__(self, duplo, base_path: str = BASE_PATH):
    self.duplo = duplo
    self.base_path = base_path
    self._api = duplo.load_client("duplo")
    self._ttl_cache = TTLCache(maxsize=128, ttl=10)

  @cachedmethod(lambda self: self._ttl_cache)
  def get(self, path: str):
    """Get an AI HelpDesk resource.

    This request is cached for 10 seconds.

    Args:
      path: The path to the resource, relative to the base path.
    Returns:
      The validated response.
    """
    return self._request("GET", path)

  def get_items(self, path: str) -> list:
    """Get every item from a paged admin list route.

    Admin data-plane list routes are server-paged and cap ``pageSize``
    at 100, so a single GET silently truncates larger collections. This
    walks the pages and accumulates ``data.items`` until ``totalCount``
    is reached (or a page comes back short/empty).

    Args:
      path: The list route relative to the base path, optionally already
        carrying a query string (e.g. ``?filters[name]=x``).

    Returns:
      Every item across all pages.
    """
    items = []
    page = 1
    sep = "&" if "?" in path else "?"
    while True:
      response = self.get(
          f"{path}{sep}page={page}&pageSize={PAGE_SIZE}").json()
      batch = unwrap_items(response)
      items.extend(batch)
      data = response.get("data")
      total = data.get("totalCount") if isinstance(data, dict) else None
      if len(batch) < PAGE_SIZE:
        break
      if isinstance(total, int) and len(items) >= total:
        break
      page += 1
    return items

  def post(self, path: str, data: dict={}, headers: dict=None, **kwargs):
    """Post data to an AI HelpDesk resource.

    Args:
      path: The path to the resource, relative to the base path.
      data: The data to post.
      headers: Optional headers merged over the default auth headers
        (e.g. ``{"Accept": "text/event-stream"}``).
      kwargs: Extra arguments forwarded to the underlying request, such
        as ``stream=True`` for SSE / chunked responses.
    Returns:
      The validated response, unbuffered when ``stream=True`` is passed.
    """
    return self._request("POST", path, json=data, extra_headers=headers, **kwargs)

  def put(self, path: str, data: dict={}):
    """Put data to an AI HelpDesk resource.

    Args:
      path: The path to the resource, relative to the base path.
      data: The data to put.
    Returns:
      The validated response.
    """
    return self._request("PUT", path, json=data)

  def delete(self, path: str):
    """Delete an AI HelpDesk resource.

    Args:
      path: The path to the resource, relative to the base path.
    Returns:
      The validated response.
    """
    return self._request("DELETE", path)

  def disable_get_cache(self) -> None:
    """Disable the get cache for this client."""
    self._ttl_cache = _NullCache()

  def _request(self, method: str, path: str, extra_headers: dict = None, **kwargs):
    headers = self._headers()
    if extra_headers:
      headers.update(extra_headers)
    try:
      response = requests.request(
        method,
        url=f"{self.duplo.host}/{self.base_path}/{path}",
        headers=headers,
        timeout=self.duplo.timeout,
        **kwargs,
      )
    except requests.exceptions.Timeout as e:
      raise DuploConnectionError("Request timed out while connecting to the AI HelpDesk") from e
    except requests.exceptions.ConnectionError as e:
      raise DuploConnectionError("Failed to establish connection with the AI HelpDesk") from e
    except requests.exceptions.RequestException as e:
      raise DuploConnectionError("Failed to send request to the AI HelpDesk") from e
    return self._validate_response(response)

  def _headers(self) -> dict:
    return {
      'Content-Type': 'application/json',
      'Authorization': f"Bearer {self._api.token}"
    }

  def _validate_response(self, response: requests.Response) -> requests.Response:
    if 200 <= response.status_code < 300:
      return response

    if response.status_code == 404:
      raise DuploNotFound(response.text)

    if response.status_code == 401:
      raise DuploError(response.text, response.status_code)

    if response.status_code == 403:
      raise DuploError(f"AI HelpDesk unauthorized: {response.text}", response.status_code)

    if response.status_code == 400:
      if "not found" in response.text.lower():
        raise DuploNotFound(response.text)
      raise DuploError(response.text, response.status_code)

    raise DuploError(
      f"AI HelpDesk responded with ({response.status_code}): {response.text}",
      response.status_code)
