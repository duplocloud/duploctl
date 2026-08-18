"""Tests for the headless (browserless) login flow.

Headless login covers remote machines and containers where no browser can be
opened. Either the user pastes back the url the browser was redirected to, or
duploctl listens on a forwarded port for the callback.
"""

import pytest
from unittest.mock import MagicMock

from duplocloud.controller import DuploCtl
from duplocloud.errors import DuploError, DuploExpiredCache, DuploInvalidError
from duplocloud.server import parse_token, HEADLESS_CALLBACK_PORT


HOST = "https://test.duplocloud.net"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.abc.def"


def _get_api(c):
  """Get the DuploAPI instance from a DuploCtl."""
  return c.load_client("duplo")


# ===========================================================================
# Token parsing
# ===========================================================================


@pytest.mark.unit
class TestParseToken:
  """Tests for duplocloud.server.parse_token()."""

  def test_parses_redirect_url(self):
    url = f"http://localhost:{HEADLESS_CALLBACK_PORT}/?t={TOKEN}"
    assert parse_token(url) == TOKEN

  def test_parses_url_with_extra_params(self):
    url = f"http://localhost:56789/?t={TOKEN}&otp=false"
    assert parse_token(url) == TOKEN

  def test_parses_scheme_less_url(self):
    """Browsers often show the address without the scheme."""
    assert parse_token(f"localhost:56789/?t={TOKEN}") == TOKEN

  def test_parses_fragment_token(self):
    assert parse_token(f"http://localhost:56789/#t={TOKEN}") == TOKEN

  def test_accepts_raw_token(self):
    """A portal that displays the token instead of redirecting."""
    assert parse_token(TOKEN) == TOKEN

  def test_strips_whitespace_and_quotes(self):
    assert parse_token(f'  "{TOKEN}" \n') == TOKEN

  def test_raises_on_empty(self):
    with pytest.raises(DuploError) as e:
      parse_token("   ")
    assert e.value.code == 403

  def test_raises_on_none(self):
    with pytest.raises(DuploError):
      parse_token(None)

  def test_raises_on_url_without_token(self):
    with pytest.raises(DuploError) as e:
      parse_token("http://localhost:56789/?success=true")
    assert e.value.code == 403


# ===========================================================================
# Flag wiring
# ===========================================================================


@pytest.mark.unit
class TestHeadlessFlags:
  """Tests for how the headless flags configure DuploCtl."""

  def test_headless_implies_interactive(self):
    c = DuploCtl(host=HOST, headless=True)
    assert c.headless is True
    assert c.interactive is True

  def test_headless_clears_given_token(self):
    c = DuploCtl(host=HOST, token=TOKEN, headless=True)
    assert c.token is None

  def test_headless_port_implies_headless(self):
    c = DuploCtl(host=HOST, headless_port=56789)
    assert c.headless is True
    assert c.interactive is True
    assert c.headless_port == 56789

  def test_headless_port_from_env_is_coerced_to_int(self):
    """Env values skip argparse type conversion and arrive as strings."""
    c = DuploCtl(host=HOST, headless_port="56789")
    assert c.headless_port == 56789

  def test_invalid_headless_port_raises(self):
    with pytest.raises(DuploInvalidError):
      DuploCtl(host=HOST, headless_port="notaport")

  def test_defaults_are_off(self):
    c = DuploCtl(host=HOST, token=TOKEN)
    assert c.headless is False
    assert c.headless_port is None

  def test_build_command_includes_headless(self):
    c = DuploCtl(host=HOST, tenant="dev", headless=True)
    cmd = c.build_command("duploctl", "jit", "aws")
    assert "--headless" in cmd
    assert "--interactive" in cmd
    assert "--headless-port" not in cmd

  def test_build_command_includes_headless_port(self):
    c = DuploCtl(host=HOST, tenant="dev", headless_port=56789)
    cmd = c.build_command("duploctl", "jit", "aws")
    assert "--headless-port" in cmd
    assert cmd[cmd.index("--headless-port") + 1] == "56789"

  def test_build_command_omits_headless_when_off(self):
    c = DuploCtl(host=HOST, tenant="dev", interactive=True)
    cmd = c.build_command("duploctl", "jit", "aws")
    assert "--headless" not in cmd


# ===========================================================================
# Headless token request
# ===========================================================================


@pytest.mark.unit
class TestHeadlessToken:
  """Tests for DuploAPI.headless_token() and its two delivery modes."""

  def test_request_token_routes_to_headless(self, mocker):
    c = DuploCtl(host=HOST, headless=True)
    api = _get_api(c)
    mock_ht = mocker.patch.object(api, "headless_token", return_value="tok")
    mock_server = mocker.patch("duplocloud.client.TokenServer")
    assert api.request_token() == "tok"
    mock_ht.assert_called_once()
    mock_server.assert_not_called()

  def test_paste_mode_url_has_default_port(self, mocker):
    c = DuploCtl(host=HOST, headless=True)
    api = _get_api(c)
    mock_paste = mocker.patch.object(api, "_pasted_token", return_value="tok")
    assert api.headless_token() == "tok"
    url = mock_paste.call_args[0][0]
    assert url.startswith(f"{HOST}/app/user/verify-token?")
    assert "localAppName=duploctl" in url
    assert f"localPort={HEADLESS_CALLBACK_PORT}" in url
    assert "isAdmin=false" in url
    assert "redirect=true" in url

  def test_paste_mode_passes_admin_flag(self, mocker):
    c = DuploCtl(host=HOST, headless=True, isadmin=True)
    api = _get_api(c)
    mock_paste = mocker.patch.object(api, "_pasted_token", return_value="tok")
    api.headless_token()
    assert "isAdmin=true" in mock_paste.call_args[0][0]

  def test_headless_port_uses_relay_mode(self, mocker):
    c = DuploCtl(host=HOST, headless_port=4444)
    api = _get_api(c)
    mock_relay = mocker.patch.object(api, "_relayed_token", return_value="tok")
    mock_paste = mocker.patch.object(api, "_pasted_token")
    assert api.headless_token() == "tok"
    mock_paste.assert_not_called()
    url, port = mock_relay.call_args[0]
    assert "localPort=4444" in url
    assert port == 4444

  def test_pasted_token_reads_redirect_url(self, mocker):
    c = DuploCtl(host=HOST, headless=True)
    api = _get_api(c)
    mocker.patch("sys.stdin.isatty", return_value=True)
    mocker.patch("builtins.input", return_value=f"http://localhost:56789/?t={TOKEN}")
    assert api._pasted_token("https://portal/login", 56789) == TOKEN

  def test_pasted_token_requires_a_tty(self, mocker):
    c = DuploCtl(host=HOST, headless=True)
    api = _get_api(c)
    mocker.patch("sys.stdin.isatty", return_value=False)
    with pytest.raises(DuploError) as e:
      api._pasted_token("https://portal/login", 56789)
    assert e.value.code == 403
    assert "--headless-port" in str(e.value)

  def test_pasted_token_cancelled(self, mocker):
    c = DuploCtl(host=HOST, headless=True)
    api = _get_api(c)
    mocker.patch("sys.stdin.isatty", return_value=True)
    mocker.patch("builtins.input", side_effect=EOFError)
    with pytest.raises(DuploError) as e:
      api._pasted_token("https://portal/login", 56789)
    assert e.value.code == 403

  def test_relayed_token_serves_on_given_port(self, mocker):
    c = DuploCtl(host=HOST, headless_port=4444)
    api = _get_api(c)
    mock_server = MagicMock()
    mock_server.serve_token.return_value = "relayed"
    mock_server.__enter__ = MagicMock(return_value=mock_server)
    mock_server.__exit__ = MagicMock(return_value=False)
    ctor = mocker.patch("duplocloud.client.TokenServer", return_value=mock_server)

    assert api._relayed_token("https://portal/login", 4444) == "relayed"

    assert ctor.call_args.kwargs["port"] == 4444

  def test_relayed_token_port_in_use(self, mocker):
    c = DuploCtl(host=HOST, headless_port=4444)
    api = _get_api(c)
    mocker.patch("duplocloud.client.TokenServer", side_effect=OSError("in use"))
    with pytest.raises(DuploError) as e:
      api._relayed_token("https://portal/login", 4444)
    assert e.value.code == 500

  def test_browser_flow_warns_when_no_browser(self, mocker):
    """A browser login that cannot launch anything points at --headless."""
    c = DuploCtl(host=HOST, interactive=True)
    api = _get_api(c)
    mock_server = MagicMock()
    mock_server.server_port = 12345
    mock_server.open_callback.return_value = False
    mock_server.serve_token.return_value = "tok"
    mock_server.__enter__ = MagicMock(return_value=mock_server)
    mock_server.__exit__ = MagicMock(return_value=False)
    mocker.patch("duplocloud.client.TokenServer", return_value=mock_server)
    mock_warn = mocker.patch.object(c.logger, "warning")

    assert api.request_token() == "tok"
    mock_warn.assert_called_once()
    assert "--headless" in mock_warn.call_args[0][0]

  def test_headless_token_is_cached(self, mocker):
    """A headless token flows through the same cache as a browser login."""
    c = DuploCtl(host=HOST, headless=True)
    api = _get_api(c)
    mocker.patch.object(api, "request_token", return_value="fresh")
    mocker.patch.object(api.cache, "get", side_effect=DuploExpiredCache("k"))
    mock_set = mocker.patch.object(api.cache, "set")
    mocker.patch.object(api.cache, "expiration", return_value="2099-01-01T00:00:00+00:00")
    assert api.interactive_token() == "fresh"
    mock_set.assert_called_once()
