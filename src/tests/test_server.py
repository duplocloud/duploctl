import threading
import time
import pytest
from unittest.mock import patch, MagicMock
from urllib.request import urlopen, Request
from urllib.error import URLError

from duplocloud.server import TokenServer, TokenCallbackHandler
from duplocloud.errors import DuploError


# --- Helpers ---

def start_server(host="https://test.example.com", timeout=5, port=0):
  """Create and return a TokenServer bound to a random port."""
  server = TokenServer(host, timeout=timeout, port=port)
  return server


def post_token(server, token):
  """Send a token to the server via POST."""
  url = f"http://127.0.0.1:{server.server_port}/"
  data = token.encode("utf-8")
  req = Request(url, data=data, method="POST")
  req.add_header("Content-Type", "text/plain")
  try:
    with urlopen(req, timeout=2) as resp:
      return resp.status
  except URLError:
    return None


def get_token(server, token):
  """Send a token to the server via GET with query param."""
  url = f"http://127.0.0.1:{server.server_port}/?t={token}"
  req = Request(url, method="GET")
  # Don't follow redirects — we just want to deliver the token
  import urllib.request
  class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
      return None
  opener = urllib.request.build_opener(NoRedirectHandler)
  try:
    opener.open(req, timeout=2)
  except urllib.error.HTTPError as e:
    return e.code
  except URLError:
    return None
  return 200


# --- Tests for TokenServer.__init__ ---

@pytest.mark.unit
class TestTokenServerInit:
  def test_default_random_port(self):
    """Server binds to a random port when port=0."""
    with start_server() as server:
      assert server.server_port > 0
      assert server.host == "https://test.example.com"
      assert server.timeout == 5
      assert server.token is None

  def test_custom_timeout(self):
    """Server respects custom timeout."""
    with start_server(timeout=10) as server:
      assert server.timeout == 10

  def test_specific_port(self):
    """Server can bind to a specific port."""
    # First get a random port, close it, then reuse it
    with start_server() as temp:
      port = temp.server_port
    with start_server(port=port) as server:
      assert server.server_port == port

  def test_two_servers_different_ports(self):
    """Two servers on port=0 get different random ports."""
    with start_server() as s1, start_server() as s2:
      assert s1.server_port != s2.server_port


# --- Tests for TokenCallbackHandler.do_POST ---

@pytest.mark.unit
class TestDoPost:
  def test_post_sets_token(self):
    """POST request delivers a token to the server."""
    with start_server() as server:
      st = threading.Thread(target=server.serve_forever)
      st.start()
      try:
        status = post_token(server, "test-token-abc")
        assert status == 200
        assert server.token == "test-token-abc"
      finally:
        server.shutdown()
        st.join(timeout=2)


# --- Tests for TokenCallbackHandler.do_GET ---

@pytest.mark.unit
class TestDoGet:
  def test_get_sets_token(self):
    """GET request with ?t=<token> delivers a token and returns 302."""
    with start_server() as server:
      st = threading.Thread(target=server.serve_forever)
      st.start()
      try:
        status = get_token(server, "get-token-xyz")
        assert status == 302
        assert server.token == "get-token-xyz"
      finally:
        server.shutdown()
        st.join(timeout=2)

  def test_get_redirect_location(self):
    """GET response redirects back to the portal success page."""
    with start_server(host="https://myportal.example.com") as server:
      st = threading.Thread(target=server.serve_forever)
      st.start()
      try:
        url = f"http://127.0.0.1:{server.server_port}/?t=tok123"
        req = Request(url, method="GET")
        import urllib.request
        class CaptureRedirectHandler(urllib.request.HTTPRedirectHandler):
          def redirect_request(self, req, fp, code, msg, headers, newurl):
            self.captured_location = newurl
            return None
        handler = CaptureRedirectHandler()
        opener = urllib.request.build_opener(handler)
        try:
          opener.open(req, timeout=2)
        except Exception:
          pass
        assert hasattr(handler, "captured_location")
        loc = handler.captured_location
        assert "myportal.example.com" in loc
        assert "success=true" in loc
        assert "duploctl" in loc
      finally:
        server.shutdown()
        st.join(timeout=2)


# --- Tests for TokenCallbackHandler.do_OPTIONS ---

@pytest.mark.unit
class TestDoOptions:
  def test_options_returns_200(self):
    """OPTIONS preflight returns 200."""
    with start_server() as server:
      st = threading.Thread(target=server.serve_forever)
      st.start()
      try:
        url = f"http://127.0.0.1:{server.server_port}/"
        req = Request(url, method="OPTIONS")
        with urlopen(req, timeout=2) as resp:
          assert resp.status == 200
      finally:
        server.shutdown()
        st.join(timeout=2)


# --- Tests for CORS headers ---

@pytest.mark.unit
class TestCorsHeaders:
  def test_cors_origin_matches_host(self):
    """Access-Control-Allow-Origin header matches the configured host."""
    with start_server(host="https://cors.example.com") as server:
      st = threading.Thread(target=server.serve_forever)
      st.start()
      try:
        url = f"http://127.0.0.1:{server.server_port}/"
        req = Request(url, method="OPTIONS")
        with urlopen(req, timeout=2) as resp:
          assert resp.headers["Access-Control-Allow-Origin"] == "https://cors.example.com"
          assert "POST" in resp.headers["Access-Control-Allow-Methods"]
          assert "GET" in resp.headers["Access-Control-Allow-Methods"]
          assert resp.headers["Cache-Control"] == "no-store, no-cache, must-revalidate"
      finally:
        server.shutdown()
        st.join(timeout=2)


# --- Tests for serve_token ---

@pytest.mark.unit
class TestServeToken:
  def test_serve_token_returns_posted_token(self):
    """serve_token() blocks until a token is POSTed, then returns it."""
    server = start_server(timeout=5)
    with server:
      def send_token_after_delay():
        time.sleep(0.3)
        post_token(server, "delayed-token")

      sender = threading.Thread(target=send_token_after_delay)
      sender.start()
      token = server.serve_token()
      sender.join(timeout=2)
      assert token == "delayed-token"

  def test_serve_token_timeout_raises(self):
    """serve_token() raises DuploError if no token received before timeout."""
    server = start_server(timeout=1)
    with server:
      with pytest.raises(DuploError) as exc_info:
        server.serve_token()
      assert exc_info.value.code == 403


# --- Tests for open_callback ---

@pytest.mark.unit
class TestOpenCallback:
  @patch("duplocloud.server.webbrowser")
  def test_open_callback_default_browser(self, mock_wb):
    """open_callback opens the correct URL in the default browser."""
    with start_server(host="https://portal.example.com") as server:
      server.open_callback("app/user/verify-token?foo=bar")
      mock_wb.open.assert_called_once_with(
        "https://portal.example.com/app/user/verify-token?foo=bar",
        new=0, autoraise=True
      )

  @patch("duplocloud.server.webbrowser")
  def test_open_callback_custom_browser(self, mock_wb):
    """open_callback uses the specified browser when provided."""
    mock_custom = MagicMock()
    mock_wb.get.return_value = mock_custom
    with start_server(host="https://portal.example.com") as server:
      server.open_callback("some/page", browser="firefox")
      mock_wb.get.assert_called_once_with("firefox")
      mock_custom.open.assert_called_once_with(
        "https://portal.example.com/some/page",
        new=0, autoraise=True
      )


# --- Tests for log suppression ---

@pytest.mark.unit
def test_log_message_suppressed(capsys):
  """TokenCallbackHandler.log_message produces no output."""
  with start_server() as server:
    st = threading.Thread(target=server.serve_forever)
    st.start()
    try:
      post_token(server, "quiet-token")
      captured = capsys.readouterr()
      assert captured.out == ""
      assert captured.err == ""
    finally:
      server.shutdown()
      st.join(timeout=2)
