import pytest
from unittest.mock import MagicMock

from duplocloud.errors import DuploError, DuploNotFound
from duplo_resource.helpdesk_client import (
  DuploHelpdeskClient,
  unwrap_data,
  unwrap_items,
)

_HOST = "https://example.duplocloud.net"
_TOKEN = "test-token"


def _make_client(token=_TOKEN):
  duplo = MagicMock()
  duplo.host = _HOST
  duplo.token = token
  duplo.timeout = 60
  duplo.load_client.return_value = MagicMock(token=token)
  return DuploHelpdeskClient(duplo)


def _mock_response(mocker, status_code=200, text="{}"):
  response = mocker.MagicMock()
  response.status_code = status_code
  response.text = text
  return mocker.patch(
    "duplo_resource.helpdesk_client.requests.request",
    return_value=response), response


@pytest.mark.unit
def test_get_builds_prefixed_url(mocker):
  client = _make_client()
  request, response = _mock_response(mocker)
  result = client.get("admin/data/workspaces")
  assert result is response
  args, kwargs = request.call_args
  assert args[0] == "GET"
  assert kwargs["url"] == f"{_HOST}/v1/aiservicedesk/admin/data/workspaces"
  assert kwargs["headers"]["Authorization"] == f"Bearer {_TOKEN}"


@pytest.mark.unit
def test_post_merges_headers_and_forwards_stream(mocker):
  client = _make_client()
  request, _ = _mock_response(mocker)
  client.post(
    "tickets/wid/DEVOPS-1/sendMessageStreaming",
    {"content": "hi"},
    headers={"Accept": "text/event-stream"},
    stream=True)
  _, kwargs = request.call_args
  assert kwargs["headers"]["Accept"] == "text/event-stream"
  assert kwargs["headers"]["Authorization"] == f"Bearer {_TOKEN}"
  assert kwargs["json"] == {"content": "hi"}
  assert kwargs["stream"] is True


@pytest.mark.unit
def test_put_and_delete_hit_prefixed_urls(mocker):
  client = _make_client()
  request, _ = _mock_response(mocker)
  client.put("admin/data/aiagents/a-1", {"id": "a-1"})
  assert request.call_args[1]["url"].endswith("/v1/aiservicedesk/admin/data/aiagents/a-1")
  client.delete("tickets/wid/DEVOPS-1")
  assert request.call_args[1]["url"].endswith("/v1/aiservicedesk/tickets/wid/DEVOPS-1")


@pytest.mark.unit
def test_404_raises_not_found(mocker):
  client = _make_client()
  _mock_response(mocker, status_code=404, text="no such workspace")
  with pytest.raises(DuploNotFound):
    client.get("admin/data/workspaces/missing")


@pytest.mark.unit
def test_400_not_found_text_raises_not_found(mocker):
  client = _make_client()
  _mock_response(mocker, status_code=400, text="Workspace not found")
  with pytest.raises(DuploNotFound):
    client.get("admin/data/workspaces/missing")


@pytest.mark.unit
def test_other_errors_raise_duplo_error(mocker):
  client = _make_client()
  _mock_response(mocker, status_code=500, text="boom")
  with pytest.raises(DuploError) as exc_info:
    client.delete("tickets/wid/DEVOPS-1")
  assert "AI HelpDesk responded with (500)" in str(exc_info.value)


@pytest.mark.unit
def test_get_is_cached_until_disabled(mocker):
  client = _make_client()
  request, _ = _mock_response(mocker)
  client.get("admin/data/workspaces")
  client.get("admin/data/workspaces")
  assert request.call_count == 1
  client.disable_get_cache()
  client.get("admin/data/workspaces")
  client.get("admin/data/workspaces")
  assert request.call_count == 3


@pytest.mark.unit
def test_get_items_walks_pages(mocker):
  client = _make_client()
  pages = {
    1: [{"id": f"w-{i}"} for i in range(100)],
    2: [{"id": f"w-{i}"} for i in range(100, 150)],
  }

  def fake_request(method, url, **kwargs):
    page = int(url.split("page=")[1].split("&")[0])
    response = mocker.MagicMock()
    response.status_code = 200
    response.json.return_value = {
      "success": True,
      "data": {"items": pages[page], "totalCount": 150},
    }
    return response

  request = mocker.patch(
    "duplo_resource.helpdesk_client.requests.request",
    side_effect=fake_request)

  items = client.get_items("admin/data/workspaces")

  assert len(items) == 150
  assert request.call_count == 2
  urls = [c.kwargs["url"] for c in request.call_args_list]
  assert "?page=1&pageSize=100" in urls[0]
  assert "?page=2&pageSize=100" in urls[1]


@pytest.mark.unit
def test_get_items_single_short_page(mocker):
  client = _make_client()
  request, response = _mock_response(mocker)
  response.json.return_value = {
    "success": True,
    "data": {"items": [{"id": "w-1"}], "totalCount": 1},
  }

  items = client.get_items("admin/data/workspaces?filters[name]=x")

  assert items == [{"id": "w-1"}]
  assert request.call_count == 1
  # An existing query string is extended, not clobbered.
  assert "filters[name]=x&page=1&pageSize=100" in request.call_args[1]["url"]


@pytest.mark.unit
def test_unwrap_data_enveloped_and_bare():
  assert unwrap_data({"success": True, "data": {"id": "w-1"}}) == {"id": "w-1"}
  assert unwrap_data({"id": "t-1", "title": "bare"}) == {"id": "t-1", "title": "bare"}


@pytest.mark.unit
def test_unwrap_items():
  enveloped = {"success": True, "data": {"items": [{"id": "w-1"}], "totalCount": 1}}
  assert unwrap_items(enveloped) == [{"id": "w-1"}]
  assert unwrap_items({"data": {}}) == []
  assert unwrap_items({}) == []


@pytest.mark.unit
def test_401_with_dahp_token_suggests_remint(mocker):
  """A standalone dahp_ API token that the backend rejects gets re-mint
  guidance instead of a raw 401 (dahp_ tokens are opaque, so expiry
  only surfaces server-side)."""
  client = _make_client(token="dahp_expired123")
  _mock_response(mocker, status_code=401, text="Unauthorized")
  with pytest.raises(DuploError, match="mint a new dahp_ token"):
    client.get("admin/data/workspaces")


@pytest.mark.unit
def test_401_with_portal_token_passes_through(mocker):
  client = _make_client()
  _mock_response(mocker, status_code=401, text="Unauthorized")
  with pytest.raises(DuploError, match="Unauthorized"):
    client.get("admin/data/workspaces")


@pytest.mark.unit
def test_standalone_host_and_dahp_token_flow_through(mocker):
  """Standalone mode is just DUPLO_HOST pointed at the helpdesk with a
  dahp_ bearer — the client needs no mode awareness."""
  hd_host = "https://helpdesk.example.duplocloud.net"
  client = _make_client(token="dahp_test123")
  client.duplo.host = hd_host
  request, _ = _mock_response(mocker)
  client.get("admin/data/workspaces")
  _, kwargs = request.call_args
  assert kwargs["url"].startswith(f"{hd_host}/v1/aiservicedesk/")
  assert kwargs["headers"]["Authorization"] == "Bearer dahp_test123"
