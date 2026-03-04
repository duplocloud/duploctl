"""Safety net tests for the auth flow, token resolution, cache operations,
HTTP request methods, and response validation after the client extension
point refactor.

The refactor split DuploClient into:
- DuploCtl (IoC container, aliased as DuploClient) — no HTTP/auth methods
- DuploAPI (duplocloud.client) — HTTP methods, token resolution, auth flow
- DuploCache (duplo_resource.cache) — filesystem cache operations

These tests target the new class structure while verifying the same
behaviors as before.
"""

import json
import os
import pytest
import requests
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, PropertyMock, patch, call

from duplocloud.controller import DuploClient
from duplocloud.errors import DuploError, DuploExpiredCache, DuploConnectionError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HOST = "https://test.duplocloud.net"
TOKEN = "test-token-abc123"


def _make_response(status_code=200, text="ok", json_data=None):
    """Create a mock requests.Response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


def _future_expiration(hours=1):
    """Return an ISO 8601 expiration string in the future."""
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00"
    )


def _past_expiration(hours=1):
    """Return an ISO 8601 expiration string in the past."""
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%S+00:00"
    )


def _get_api(c):
    """Get the DuploAPI instance from a DuploCtl/DuploClient."""
    return c.load_client("duplo")


def _get_cache(c):
    """Get the DuploCache instance from a DuploCtl/DuploClient."""
    return c.load("cache")


# ===========================================================================
# 0.1 Token property resolution tests
# ===========================================================================


@pytest.mark.unit
class TestTokenProperty:
    """Tests for token resolution on the DuploAPI client."""

    def test_token_returns_provided_token(self):
        c = DuploClient(host=HOST, token=TOKEN)
        assert _get_api(c).token == TOKEN

    def test_token_strips_whitespace(self):
        c = DuploClient(host=HOST, token="  tok  ")
        assert _get_api(c).token == "tok"

    def test_token_raises_when_no_host(self, mocker):
        config = "---\ncurrent-context: ctx\ncontexts:\n- name: ctx\n  tenant: t\n  token: t\n"
        mocker.patch("builtins.open", mocker.mock_open(read_data=config))
        mocker.patch("os.path.exists", return_value=True)
        c = DuploClient()
        with pytest.raises(DuploError, match="Host"):
            _ = _get_api(c).token

    def test_token_raises_when_missing_and_not_interactive(self):
        c = DuploClient(host=HOST)
        with pytest.raises(DuploError, match="Token"):
            _ = _get_api(c).token

    def test_token_calls_interactive_when_flag_set(self, mocker):
        c = DuploClient(host=HOST, interactive=True)
        api = _get_api(c)
        mocker.patch.object(api, "interactive_token", return_value="itoken")
        assert api.token == "itoken"

    def test_token_ignores_provided_token_in_interactive_mode(self, mocker):
        c = DuploClient(host=HOST, token="given", interactive=True)
        api = _get_api(c)
        mocker.patch.object(api, "interactive_token", return_value="interactive")
        # Constructor clears token when interactive=True
        assert api.token == "interactive"

    def test_token_is_lazy_not_called_until_accessed(self, mocker):
        c = DuploClient(host=HOST, interactive=True)
        api = _get_api(c)
        mock_it = mocker.patch.object(api, "interactive_token", return_value="lazy")
        # Not accessed yet
        mock_it.assert_not_called()
        # Now access it
        _ = api.token
        mock_it.assert_called_once()


# ===========================================================================
# 0.2 Interactive token flow tests
# ===========================================================================


@pytest.mark.unit
class TestInteractiveTokenFlow:
    """Tests for DuploAPI.interactive_token()."""

    def test_returns_cached_when_valid(self, mocker):
        c = DuploClient(host=HOST, interactive=True)
        api = _get_api(c)
        cache_data = {"DuploToken": "cached", "Expiration": _future_expiration()}
        mocker.patch.object(api.cache, "get", return_value=cache_data)
        mocker.patch.object(api.cache, "expired", return_value=False)
        mock_request = mocker.patch.object(api, "request_token")

        result = api.interactive_token()
        assert result == "cached"
        mock_request.assert_not_called()

    def test_requests_fresh_when_cache_expired(self, mocker):
        c = DuploClient(host=HOST, interactive=True)
        api = _get_api(c)
        cache_data = {"DuploToken": "old", "Expiration": _past_expiration()}
        mocker.patch.object(api.cache, "get", return_value=cache_data)
        mocker.patch.object(api.cache, "expired", return_value=True)
        mocker.patch.object(api, "request_token", return_value="fresh")
        mock_set = mocker.patch.object(api.cache, "set")
        mocker.patch.object(api.cache, "expiration", return_value=_future_expiration())

        result = api.interactive_token()
        assert result == "fresh"
        mock_set.assert_called_once()

    def test_requests_fresh_when_no_cache_file(self, mocker):
        c = DuploClient(host=HOST, interactive=True)
        api = _get_api(c)
        mocker.patch.object(
            api.cache, "get", side_effect=DuploExpiredCache("key")
        )
        mocker.patch.object(api, "request_token", return_value="fresh")
        mock_set = mocker.patch.object(api.cache, "set")
        mocker.patch.object(api.cache, "expiration", return_value=_future_expiration())

        result = api.interactive_token()
        assert result == "fresh"
        mock_set.assert_called_once()

    def test_skips_cache_when_nocache_flag(self, mocker):
        c = DuploClient(host=HOST, interactive=True, nocache=True)
        api = _get_api(c)
        mock_get = mocker.patch.object(api.cache, "get")
        mock_set = mocker.patch.object(api.cache, "set")
        mocker.patch.object(api, "request_token", return_value="nocache_tok")

        result = api.interactive_token()
        assert result == "nocache_tok"
        mock_get.assert_not_called()
        mock_set.assert_not_called()

    def test_caches_with_correct_structure(self, mocker):
        c = DuploClient(host=HOST, interactive=True)
        api = _get_api(c)
        mocker.patch.object(
            api.cache, "get", side_effect=DuploExpiredCache("key")
        )
        mocker.patch.object(api, "request_token", return_value="newtoken")
        mock_set = mocker.patch.object(api.cache, "set")
        mocker.patch.object(api.cache, "expiration", return_value=_future_expiration())

        api.interactive_token()

        # Verify the structure of what was cached
        _, kwargs = mock_set.call_args
        if not kwargs:
            args = mock_set.call_args[0]
            cached = args[1]
        else:
            cached = kwargs.get("data", mock_set.call_args[0][1])

        assert cached["Version"] == "v1"
        assert cached["DuploToken"] == "newtoken"
        assert "Expiration" in cached
        assert cached["NeedOTP"] is False
        # Verify expiration is a valid future datetime
        exp_dt = datetime.fromisoformat(cached["Expiration"])
        assert exp_dt > datetime.now(timezone.utc)


# ===========================================================================
# 0.3 Cached token validation tests
# ===========================================================================


@pytest.mark.unit
class TestCachedToken:
    """Tests for DuploAPI.cached_token()."""

    def test_returns_token_when_not_expired(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        cache_data = {"DuploToken": "valid_tok", "Expiration": _future_expiration()}
        mocker.patch.object(api.cache, "get", return_value=cache_data)
        mocker.patch.object(api.cache, "expired", return_value=False)
        assert api.cached_token("key") == "valid_tok"

    def test_raises_when_expired(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        cache_data = {"DuploToken": "old_tok", "Expiration": _past_expiration()}
        mocker.patch.object(api.cache, "get", return_value=cache_data)
        mocker.patch.object(api.cache, "expired", return_value=True)
        with pytest.raises(DuploExpiredCache):
            api.cached_token("key")

    def test_raises_when_missing_expiration_key(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        cache_data = {"DuploToken": "tok"}  # No Expiration
        mocker.patch.object(api.cache, "get", return_value=cache_data)
        with pytest.raises(DuploExpiredCache):
            api.cached_token("key")

    def test_raises_when_missing_token_key(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        cache_data = {"Expiration": _future_expiration()}  # No DuploToken
        mocker.patch.object(api.cache, "get", return_value=cache_data)
        with pytest.raises(DuploExpiredCache):
            api.cached_token("key")

    def test_raises_when_cache_file_missing(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mocker.patch.object(
            api.cache, "get", side_effect=DuploExpiredCache("key")
        )
        with pytest.raises(DuploExpiredCache):
            api.cached_token("key")


# ===========================================================================
# 0.4 Request token (browser login) tests
# ===========================================================================


@pytest.mark.unit
class TestRequestToken:
    """Tests for DuploAPI.request_token()."""

    def test_opens_browser_with_correct_url(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_server = MagicMock()
        mock_server.server_port = 12345
        mock_server.serve_token.return_value = "browsertoken"
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)
        mocker.patch("duplocloud.client.TokenServer", return_value=mock_server)

        api.request_token()

        mock_server.open_callback.assert_called_once()
        page_arg = mock_server.open_callback.call_args[0][0]
        assert "app/user/verify-token" in page_arg
        assert "localAppName=duploctl" in page_arg
        assert "localPort=12345" in page_arg
        assert "isAdmin=false" in page_arg

    def test_passes_admin_flag(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN, isadmin=True)
        api = _get_api(c)
        mock_server = MagicMock()
        mock_server.server_port = 12345
        mock_server.serve_token.return_value = "tok"
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)
        mocker.patch("duplocloud.client.TokenServer", return_value=mock_server)

        api.request_token()

        page_arg = mock_server.open_callback.call_args[0][0]
        assert "isAdmin=true" in page_arg

    def test_passes_browser_param(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN, browser="firefox")
        api = _get_api(c)
        mock_server = MagicMock()
        mock_server.server_port = 12345
        mock_server.serve_token.return_value = "tok"
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)
        mocker.patch("duplocloud.client.TokenServer", return_value=mock_server)

        api.request_token()

        browser_arg = mock_server.open_callback.call_args[0][1]
        assert browser_arg == "firefox"

    def test_returns_server_token(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_server = MagicMock()
        mock_server.server_port = 12345
        mock_server.serve_token.return_value = "browsertoken"
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)
        mocker.patch("duplocloud.client.TokenServer", return_value=mock_server)

        result = api.request_token()
        assert result == "browsertoken"

    def test_handles_keyboard_interrupt(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_server = MagicMock()
        mock_server.server_port = 12345
        mock_server.serve_token.side_effect = KeyboardInterrupt
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)
        mocker.patch("duplocloud.client.TokenServer", return_value=mock_server)

        api.request_token()
        mock_server.shutdown.assert_called_once()


# ===========================================================================
# 0.5 Cache utility tests
# ===========================================================================


@pytest.mark.unit
class TestCacheUtilities:
    """Tests for DuploCache: key_for, expired, expiration, get, set."""

    def test_cache_key_for_basic(self):
        c = DuploClient(host="https://portal.duplo.com", token=TOKEN)
        cache = _get_cache(c)
        key = cache.key_for("duplo-creds")
        assert key == "portal.duplo.com,duplo-creds"

    def test_cache_key_for_with_admin(self):
        c = DuploClient(host="https://portal.duplo.com", token=TOKEN, isadmin=True)
        cache = _get_cache(c)
        key = cache.key_for("duplo-creds")
        assert key == "portal.duplo.com,admin,duplo-creds"

    def test_cache_key_for_strips_scheme(self):
        c = DuploClient(host="https://portal.duplo.com", token=TOKEN)
        cache = _get_cache(c)
        key = cache.key_for("test")
        assert "https://" not in key
        assert "portal.duplo.com" in key

    def test_expired_with_none_returns_true(self):
        c = DuploClient(host=HOST, token=TOKEN)
        cache = _get_cache(c)
        assert cache.expired(None) is True

    def test_expired_with_future_returns_false(self):
        c = DuploClient(host=HOST, token=TOKEN)
        cache = _get_cache(c)
        assert cache.expired(_future_expiration()) is False

    def test_expired_with_past_returns_true(self):
        c = DuploClient(host=HOST, token=TOKEN)
        cache = _get_cache(c)
        assert cache.expired(_past_expiration()) is True

    def test_expiration_returns_future_iso8601(self):
        c = DuploClient(host=HOST, token=TOKEN)
        cache = _get_cache(c)
        exp_str = cache.expiration(1)
        exp_dt = datetime.fromisoformat(exp_str)
        now = datetime.now(timezone.utc)
        # Should be roughly 1 hour from now (within 5 seconds tolerance)
        diff = (exp_dt - now).total_seconds()
        assert 3595 < diff < 3605

    def test_expiration_custom_hours(self):
        c = DuploClient(host=HOST, token=TOKEN)
        cache = _get_cache(c)
        exp_str = cache.expiration(2)
        exp_dt = datetime.fromisoformat(exp_str)
        now = datetime.now(timezone.utc)
        diff = (exp_dt - now).total_seconds()
        assert 7195 < diff < 7205

    def test_get_reads_json_file(self, tmp_path):
        cache_dir = str(tmp_path)
        c = DuploClient(host=HOST, token=TOKEN, cache_dir=cache_dir)
        cache = _get_cache(c)
        data = {"foo": "bar", "num": 42}
        # Write directly to filesystem
        with open(tmp_path / "testkey.json", "w") as f:
            json.dump(data, f)
        result = cache.get("testkey")
        assert result == data

    def test_get_raises_when_file_missing(self, tmp_path):
        c = DuploClient(host=HOST, token=TOKEN, cache_dir=str(tmp_path))
        cache = _get_cache(c)
        with pytest.raises(DuploExpiredCache):
            cache.get("nonexistent")

    def test_get_raises_on_malformed_json(self, tmp_path):
        c = DuploClient(host=HOST, token=TOKEN, cache_dir=str(tmp_path))
        cache = _get_cache(c)
        with open(tmp_path / "bad.json", "w") as f:
            f.write("not valid json {{{")
        with pytest.raises(DuploExpiredCache):
            cache.get("bad")

    def test_set_writes_json_file(self, tmp_path):
        cache_dir = str(tmp_path)
        c = DuploClient(host=HOST, token=TOKEN, cache_dir=cache_dir)
        cache = _get_cache(c)
        data = {"key": "value"}
        cache.set("mykey", data)
        with open(tmp_path / "mykey.json", "r") as f:
            assert json.load(f) == data

    def test_set_creates_cache_dir(self, tmp_path):
        cache_dir = str(tmp_path / "new_cache_dir")
        assert not os.path.exists(cache_dir)
        c = DuploClient(host=HOST, token=TOKEN, cache_dir=cache_dir)
        cache = _get_cache(c)
        cache.set("test", {"a": 1})
        assert os.path.exists(cache_dir)
        assert os.path.exists(os.path.join(cache_dir, "test.json"))


# ===========================================================================
# 0.6 HTTP request method tests
# ===========================================================================


@pytest.mark.unit
class TestHTTPMethods:
    """Tests for DuploAPI.get/post/put/delete and _request."""

    def test_get_calls_request_with_get_method(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_req = mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(200),
        )
        api.get("api/path")
        mock_req.assert_called_once()
        call_args = mock_req.call_args
        method = call_args[0][0] if call_args[0] else call_args.kwargs["method"]
        assert method == "GET"

    def test_get_constructs_correct_url(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_req = mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(200),
        )
        api.get("api/v3/resource")
        call_kwargs = mock_req.call_args
        url = call_kwargs.kwargs.get("url") or call_kwargs[1].get("url")
        assert url == f"{HOST}/api/v3/resource"

    def test_get_includes_auth_headers(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_req = mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(200),
        )
        api.get("path")
        call_kwargs = mock_req.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Authorization"] == f"Bearer {TOKEN}"
        assert headers["Content-Type"] == "application/json"

    def test_get_includes_timeout(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_req = mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(200),
        )
        api.get("path")
        call_kwargs = mock_req.call_args
        timeout = call_kwargs.kwargs.get("timeout") or call_kwargs[1].get("timeout")
        assert timeout == 60

    def test_post_sends_json_data(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_req = mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(200),
        )
        api.post("api/path", {"key": "val"})
        call_kwargs = mock_req.call_args
        json_data = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert json_data == {"key": "val"}

    def test_put_sends_json_data(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_req = mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(200),
        )
        api.put("api/path", {"update": True})
        call_kwargs = mock_req.call_args
        json_data = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert json_data == {"update": True}

    def test_delete_calls_correct_method(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_req = mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(200),
        )
        api.delete("api/path")
        call_args = mock_req.call_args
        method = call_args[0][0] if call_args[0] else call_args.kwargs.get("method")
        assert method == "DELETE"

    def test_get_caches_identical_requests(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_req = mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(200),
        )
        api.get("same/path")
        api.get("same/path")
        # TTL cache should prevent second call
        assert mock_req.call_count == 1

    def test_get_cache_different_paths_not_cached(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_req = mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(200),
        )
        api.get("path/a")
        api.get("path/b")
        assert mock_req.call_count == 2

    def test_request_raises_on_timeout(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mocker.patch(
            "duplocloud.client.requests.request",
            side_effect=requests.exceptions.Timeout("timed out"),
        )
        with pytest.raises(DuploConnectionError):
            api.get("path")

    def test_request_raises_on_connection_error(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mocker.patch(
            "duplocloud.client.requests.request",
            side_effect=requests.exceptions.ConnectionError("conn failed"),
        )
        with pytest.raises(DuploConnectionError):
            api.post("path", {})

    def test_request_raises_on_request_exception(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mocker.patch(
            "duplocloud.client.requests.request",
            side_effect=requests.exceptions.RequestException("generic"),
        )
        with pytest.raises(DuploConnectionError):
            api.put("path", {})


# ===========================================================================
# 0.7 Response validation tests
# ===========================================================================


@pytest.mark.unit
class TestResponseValidation:
    """Tests for DuploAPI._validate_response, tested indirectly through
    get/post since _validate_response is private."""

    def test_response_200_returns_response(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_resp = _make_response(200)
        mocker.patch("duplocloud.client.requests.request", return_value=mock_resp)
        result = api.get("path")
        assert result == mock_resp

    def test_response_201_returns_response(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_resp = _make_response(201)
        mocker.patch("duplocloud.client.requests.request", return_value=mock_resp)
        result = api.post("path", {})
        assert result == mock_resp

    def test_response_404_raises_not_found(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(404, "not found"),
        )
        with pytest.raises(DuploError) as exc_info:
            api.get("path")
        assert exc_info.value.code == 404

    def test_response_401_raises_auth_error(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(401, "unauthorized"),
        )
        with pytest.raises(DuploError) as exc_info:
            api.post("path", {})
        assert exc_info.value.code == 401

    def test_response_403_raises_unauthorized(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(403, "forbidden"),
        )
        with pytest.raises(DuploError) as exc_info:
            api.put("path", {})
        assert exc_info.value.code == 403
        assert "Unauthorized" in str(exc_info.value.message)

    def test_response_400_raises_error(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(400, "bad request"),
        )
        with pytest.raises(DuploError) as exc_info:
            api.delete("path")
        assert exc_info.value.code == 400

    def test_response_500_raises_error(self, mocker):
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mocker.patch(
            "duplocloud.client.requests.request",
            return_value=_make_response(500, "server error"),
        )
        with pytest.raises(DuploError) as exc_info:
            api.post("path", {})
        assert exc_info.value.code == 500


# ===========================================================================
# 0.8 Constructor edge case tests
# ===========================================================================


@pytest.mark.unit
class TestConstructorEdgeCases:
    """Tests for arg-processing logic in DuploCtl.__init__."""

    def test_context_flag_clears_host_and_token(self, mocker):
        config = (
            "---\ncurrent-context: myctx\ncontexts:\n"
            "- name: myctx\n  host: https://ctx.host.com\n  token: ctxtoken\n"
        )
        mocker.patch("builtins.open", mocker.mock_open(read_data=config))
        mocker.patch("os.path.exists", return_value=True)
        c = DuploClient(host="https://explicit.com", token="explicit", ctx="myctx")
        # ctx overrides: host comes from context, not from explicit arg
        assert c.host == "https://ctx.host.com"
        assert _get_api(c).token == "ctxtoken"

    def test_interactive_flag_clears_token(self, mocker):
        c = DuploClient(host=HOST, token="given", interactive=True)
        api = _get_api(c)
        mocker.patch.object(api, "interactive_token", return_value="interactive")
        # token arg was cleared by interactive flag
        assert api.token == "interactive"

    def test_tenant_id_clears_tenant_name(self):
        c = DuploClient(host=HOST, token=TOKEN, tenant="myname", tenant_id="tid123")
        assert c.tenant is None
        assert c.tenantid == "tid123"

    def test_from_creds_sets_all_fields(self):
        c = DuploClient.from_creds("https://x.com", "tok", "ten")
        assert c.host == "https://x.com"
        assert _get_api(c).token == "tok"
        assert c.tenant == "ten"


# ===========================================================================
# 0.9 Full auth flow integration tests (mocked)
# ===========================================================================


@pytest.mark.unit
class TestFullAuthFlow:
    """End-to-end scenario tests exercising the complete call chain."""

    def test_full_flow_token_from_env(self, mocker):
        """Client with explicit host+token makes a GET with correct auth."""
        c = DuploClient(host=HOST, token=TOKEN)
        api = _get_api(c)
        mock_resp = _make_response(200, json_data={"result": "ok"})
        mock_req = mocker.patch(
            "duplocloud.client.requests.request", return_value=mock_resp
        )

        result = api.get("api/test")

        assert result.json() == {"result": "ok"}
        call_kwargs = mock_req.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Authorization"] == f"Bearer {TOKEN}"

    def test_full_flow_interactive_cached(self, mocker):
        """Interactive mode with valid cache: uses cached token, no browser."""
        c = DuploClient(host=HOST, interactive=True)
        api = _get_api(c)
        cache_data = {"DuploToken": "cached_tok", "Expiration": _future_expiration()}
        mocker.patch.object(api.cache, "get", return_value=cache_data)
        mocker.patch.object(api.cache, "expired", return_value=False)
        mock_server_cls = mocker.patch("duplocloud.client.TokenServer")
        mock_resp = _make_response(200)
        mock_req = mocker.patch(
            "duplocloud.client.requests.request", return_value=mock_resp
        )

        result = api.get("api/test")

        # Browser NOT opened
        mock_server_cls.assert_not_called()
        # Auth header uses cached token
        headers = mock_req.call_args.kwargs.get("headers") or mock_req.call_args[1].get("headers")
        assert headers["Authorization"] == "Bearer cached_tok"

    def test_full_flow_interactive_expired_cache(self, mocker):
        """Interactive mode with expired cache: opens browser, caches new token."""
        c = DuploClient(host=HOST, interactive=True)
        api = _get_api(c)
        expired_cache = {"DuploToken": "old", "Expiration": _past_expiration()}
        mocker.patch.object(api.cache, "get", return_value=expired_cache)
        mocker.patch.object(api.cache, "expired", return_value=True)
        mock_set = mocker.patch.object(api.cache, "set")
        mocker.patch.object(api.cache, "expiration", return_value=_future_expiration())

        # Mock browser login
        mock_server = MagicMock()
        mock_server.server_port = 9999
        mock_server.serve_token.return_value = "new_browser_tok"
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)
        mocker.patch("duplocloud.client.TokenServer", return_value=mock_server)

        mock_resp = _make_response(200)
        mock_req = mocker.patch(
            "duplocloud.client.requests.request", return_value=mock_resp
        )

        result = api.get("api/test")

        # New token used in headers
        headers = mock_req.call_args.kwargs.get("headers") or mock_req.call_args[1].get("headers")
        assert headers["Authorization"] == "Bearer new_browser_tok"
        # New token cached
        mock_set.assert_called_once()
        cached = mock_set.call_args[0][1]
        assert cached["DuploToken"] == "new_browser_tok"

    def test_full_flow_interactive_nocache(self, mocker):
        """Interactive mode with nocache: opens browser, never reads/writes cache."""
        c = DuploClient(host=HOST, interactive=True, nocache=True)
        api = _get_api(c)
        mock_get_cache = mocker.patch.object(api.cache, "get")
        mock_set_cache = mocker.patch.object(api.cache, "set")

        mock_server = MagicMock()
        mock_server.server_port = 9999
        mock_server.serve_token.return_value = "nc_tok"
        mock_server.__enter__ = MagicMock(return_value=mock_server)
        mock_server.__exit__ = MagicMock(return_value=False)
        mocker.patch("duplocloud.client.TokenServer", return_value=mock_server)

        mock_resp = _make_response(200)
        mock_req = mocker.patch(
            "duplocloud.client.requests.request", return_value=mock_resp
        )

        result = api.get("api/test")

        # Auth header uses browser token
        headers = mock_req.call_args.kwargs.get("headers") or mock_req.call_args[1].get("headers")
        assert headers["Authorization"] == "Bearer nc_tok"
        # Cache never touched
        mock_get_cache.assert_not_called()
        mock_set_cache.assert_not_called()
