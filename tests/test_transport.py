import pytest
from yarl import URL

from aiosteampy.transport.base import BaseSteamTransport
from aiosteampy.transport.cookie import Cookie
from aiosteampy.transport.exceptions import NetworkError, TransportError, TransportResponseError
from aiosteampy.transport.resp import TransportResponse


class TestBaseSteamTransportInterface:
    """Test that both implementations satisfy the BaseSteamTransport interface."""

    @pytest.mark.asyncio
    async def test_implements_base_interface(self, transport):
        """Verify transport implements all required abstract methods."""
        assert isinstance(transport, BaseSteamTransport)
        assert hasattr(transport, "proxy")
        assert hasattr(transport, "get_cookie")
        assert hasattr(transport, "add_cookie")
        assert hasattr(transport, "remove_cookie")
        assert hasattr(transport, "get_cookies")
        assert hasattr(transport, "request")
        assert hasattr(transport, "close")

    def test_proxy_property(self, transport):
        """Verify proxy property returns None or string."""
        proxy = transport.proxy
        assert proxy is None or isinstance(proxy, str)


class TestBasicRequests:
    """Test basic HTTP request functionality."""

    @pytest.mark.asyncio
    async def test_get_request_text_mode(self, transport, test_url):
        """Test basic GET request with text response mode."""
        resp = await transport.request("GET", test_url, response_mode="text")

        assert isinstance(resp, TransportResponse)
        assert resp.status == 200
        assert resp.ok
        assert isinstance(resp.content, str)
        assert len(resp.content) > 0

    @pytest.mark.asyncio
    async def test_get_request_json_mode(self, transport, test_url):
        """Test GET request with JSON response mode."""
        resp = await transport.request("GET", test_url, response_mode="json")

        assert resp.status == 200
        assert isinstance(resp.content, dict)
        # The browser-info endpoint returns client info
        assert "clientIp" in resp.content or "ip" in resp.content

    @pytest.mark.asyncio
    async def test_get_request_bytes_mode(self, transport, test_url):
        """Test GET request with bytes response mode."""
        resp = await transport.request("GET", test_url, response_mode="bytes")

        assert resp.status == 200
        assert isinstance(resp.content, bytes)
        assert len(resp.content) > 0

    @pytest.mark.asyncio
    async def test_get_request_meta_mode(self, transport, test_url):
        """Test GET request with meta response mode (no body)."""
        resp = await transport.request("GET", test_url, response_mode="meta")

        assert resp.status == 200
        assert resp.content is None
        assert resp.headers is not None

    @pytest.mark.asyncio
    async def test_post_request_json_payload(self, transport, test_url):
        """Test POST request with JSON payload."""
        payload = {"test": "data", "value": 123}
        resp = await transport.request(
            "POST",
            test_url,
            json=payload,
            response_mode="json",
        )

        assert resp.status == 200
        assert isinstance(resp.content, dict)

    @pytest.mark.asyncio
    async def test_post_request_form_data(self, transport, test_url):
        """Test POST request with form data."""
        data = {"key": "value", "another": "field"}
        resp = await transport.request(
            "POST",
            test_url,
            data=data,
            response_mode="json",
        )

        assert resp.status == 200

    @pytest.mark.asyncio
    async def test_request_with_query_params(self, transport, test_url):
        """Test request with query parameters."""
        params = {"param1": "value1", "param2": "value2"}
        resp = await transport.request(
            "GET",
            test_url,
            params=params,
            response_mode="text",
        )

        assert resp.status == 200
        assert "param1" in str(resp.url) or resp.url.query.get("param1") == "value1"

    @pytest.mark.asyncio
    async def test_request_with_custom_headers(self, transport, test_url):
        """Test request with custom headers."""
        headers = {"X-Custom-Header": "custom-value"}
        resp = await transport.request(
            "GET",
            test_url,
            headers=headers,
            response_mode="text",
        )

        assert resp.status == 200


class TestResponseObject:
    """Test TransportResponse object attributes."""

    @pytest.mark.asyncio
    async def test_response_url(self, transport, test_url):
        """Verify response contains correct URL."""
        resp = await transport.request("GET", test_url)

        assert isinstance(resp.url, URL)
        assert str(test_url) in str(resp.url)

    @pytest.mark.asyncio
    async def test_response_status(self, transport, test_url):
        """Verify response contains status code."""
        resp = await transport.request("GET", test_url)

        assert isinstance(resp.status, int)
        assert resp.status == 200

    @pytest.mark.asyncio
    async def test_response_headers(self, transport, test_url):
        """Verify response contains headers."""
        resp = await transport.request("GET", test_url)

        assert resp.headers is not None
        assert len(resp.headers) > 0
        # Common headers that should be present
        assert "content-type" in resp.headers or "Content-Type" in resp.headers

    @pytest.mark.asyncio
    async def test_response_ok_property(self, transport, test_url):
        """Verify response.ok property works correctly."""
        resp = await transport.request("GET", test_url)

        assert resp.ok is True
        assert resp.status < 400


class TestCookieManagement:
    """Test cookie management across both implementations."""

    def test_add_and_get_cookie(self, transport, steam_login_url, sample_cookie_data):
        """Test adding and retrieving a cookie."""
        cookie = Cookie(**sample_cookie_data)
        transport.add_cookie(cookie)

        retrieved = transport.get_cookie(steam_login_url, cookie.name)
        assert retrieved is not None
        assert retrieved.name == cookie.name
        assert retrieved.value == cookie.value

    def test_get_nonexistent_cookie(self, transport, steam_login_url):
        """Test getting a cookie that doesn't exist."""
        result = transport.get_cookie(steam_login_url, "nonexistent_cookie")
        assert result is None

    def test_get_cookie_value(self, transport, steam_login_url, sample_cookie_data):
        """Test getting cookie value directly."""
        cookie = Cookie(**sample_cookie_data)
        transport.add_cookie(cookie)

        value = transport.get_cookie_value(steam_login_url, cookie.name)
        assert value == cookie.value

    def test_get_cookie_value_nonexistent(self, transport, steam_login_url):
        """Test getting value of nonexistent cookie."""
        value = transport.get_cookie_value(steam_login_url, "nonexistent")
        assert value is None

    def test_has_cookie(self, transport, steam_login_url, sample_cookie_data):
        """Test checking cookie existence."""
        cookie = Cookie(**sample_cookie_data)

        assert not transport.has_cookie(steam_login_url, cookie.name)

        transport.add_cookie(cookie)
        assert transport.has_cookie(steam_login_url, cookie.name)

    def test_remove_cookie(self, transport, steam_login_url, sample_cookie_data):
        """Test removing a cookie."""
        cookie = Cookie(**sample_cookie_data)
        transport.add_cookie(cookie)

        assert transport.has_cookie(steam_login_url, cookie.name)

        transport.remove_cookie(steam_login_url, cookie.name)
        assert not transport.has_cookie(steam_login_url, cookie.name)

    def test_get_all_cookies(self, transport, steam_login_url):
        """Test retrieving all cookies."""
        cookies_data = [
            {"name": "cookie1", "value": "value1", "domain": "steamcommunity.com", "path": "/"},
            {"name": "cookie2", "value": "value2", "domain": "steamcommunity.com", "path": "/"},
        ]

        for data in cookies_data:
            transport.add_cookie(Cookie(**data))

        all_cookies = transport.get_cookies()
        assert len(all_cookies) >= 2

        cookie_names = {c.name for c in all_cookies}
        assert "cookie1" in cookie_names
        assert "cookie2" in cookie_names

    def test_update_cookies(self, transport):
        """Test updating multiple cookies at once."""
        cookies = [
            Cookie(name="c1", value="v1", domain="steamcommunity.com", path="/"),
            Cookie(name="c2", value="v2", domain="steamcommunity.com", path="/"),
        ]

        transport.update_cookies(cookies)

        all_cookies = transport.get_cookies()
        cookie_names = {c.name for c in all_cookies}
        assert "c1" in cookie_names
        assert "c2" in cookie_names

    def test_cookie_serialization(self, transport, sample_cookie_data):
        """Test cookie serialization and deserialization."""
        cookie = Cookie(**sample_cookie_data)
        transport.add_cookie(cookie)

        serialized = transport.get_serialized_cookies()
        assert isinstance(serialized, list)
        assert len(serialized) >= 1

        # Find our cookie
        found = False
        for item in serialized:
            if item.get("name") == cookie.name:
                found = True
                assert item["value"] == cookie.value
                assert item["domain"] == cookie.domain
                break

        assert found, "Serialized cookie not found"

    def test_update_serialized_cookies(self, transport, steam_login_url, sample_cookie_data):
        """Test updating cookies from serialized format."""

        pre_serialized_cookie = Cookie(**sample_cookie_data)

        serialized = [pre_serialized_cookie.serialize()]

        transport.update_serialized_cookies(serialized)

        cookie = transport.get_cookie(steam_login_url, pre_serialized_cookie.name)
        assert cookie is not None
        assert cookie.value == pre_serialized_cookie.value


class TestErrorHandling:
    """Test error handling and exceptions."""

    @pytest.mark.asyncio
    async def test_mutually_exclusive_payloads(self, transport, test_url):
        """Test that data, json, and multipart are mutually exclusive."""
        with pytest.raises(ValueError, match="mutually exclusive"):
            await transport.request(
                "POST",
                test_url,
                data={"key": "value"},
                json={"key": "value"},
            )

    @pytest.mark.asyncio
    async def test_invalid_url_raises_transport_error(self, transport):
        """Test that invalid URLs raise TransportError."""
        invalid_url = URL("https://this-domain-definitely-does-not-exist-12345.com")

        with pytest.raises((TransportError, NetworkError)):
            await transport.request("GET", invalid_url, response_mode="text")

    @pytest.mark.asyncio
    async def test_raise_for_status_false(self, transport):
        """Test that raise_for_status=False doesn't raise exceptions."""
        # Use a URL that will return 404
        not_found_url = URL("https://api.apify.com/v2/this-endpoint-does-not-exist")

        resp = await transport.request(
            "GET",
            not_found_url,
            raise_for_status=False,
            response_mode="text",
        )

        assert resp.status == 404
        assert not resp.ok

    @pytest.mark.asyncio
    async def test_raise_for_status_true(self, transport):
        """Test that raise_for_status=True raises exceptions for errors."""
        not_found_url = URL("https://api.apify.com/v2/this-endpoint-does-not-exist")

        with pytest.raises(TransportResponseError):
            await transport.request(
                "GET",
                not_found_url,
                raise_for_status=True,
                response_mode="text",
            )


class TestRedirects:
    """Test redirect handling."""

    @pytest.mark.asyncio
    async def test_redirects_disabled(self, transport):
        """Test that redirects=False doesn't follow redirects."""
        # Using httpbin redirect endpoint if available, or skip
        redirect_url = URL("https://httpbin.org/redirect/1")

        try:
            resp = await transport.request(
                "GET",
                redirect_url,
                redirects=False,
                raise_for_status=False,
                response_mode="meta",
            )

            # Should get a 3xx redirect response
            assert 300 <= resp.status < 400
            assert len(resp.history) == 0
        except (TransportError, NetworkError):
            pytest.skip("httpbin.org not available")

    @pytest.mark.asyncio
    async def test_redirects_enabled(self, transport):
        """Test that redirects=True follows redirects."""
        redirect_url = URL("https://httpbin.org/redirect/1")

        try:
            resp = await transport.request(
                "GET",
                redirect_url,
                redirects=True,
                response_mode="meta",
            )

            # Should follow redirect and get final response
            assert resp.status == 200
            assert len(resp.history) >= 1
        except (TransportError, NetworkError):
            pytest.skip("httpbin.org not available")


class TestResourceManagement:
    """Test resource management and cleanup."""

    @pytest.mark.asyncio
    async def test_close_method_exists(self, transport):
        """Test that close method can be called."""
        # Should not raise any exception
        await transport.close()

    @pytest.mark.asyncio
    async def test_multiple_close_calls(self, transport):
        """Test that calling close multiple times is safe."""
        await transport.close()
        await transport.close()  # Should not raise


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_empty_response_body(self, transport):
        """Test handling of empty response body."""
        # HEAD requests typically have no body
        try:
            resp = await transport.request(
                "HEAD",
                URL("https://api.apify.com/v2/browser-info"),
                response_mode="text",
                raise_for_status=False,
            )

            assert resp.content is None or resp.content == "" or resp.content == b""
        except Exception:
            # Some implementations may not support HEAD
            pytest.skip("HEAD method not properly supported")

    @pytest.mark.asyncio
    async def test_request_with_empty_params(self, transport, test_url):
        """Test request with empty query parameters."""
        resp = await transport.request(
            "GET",
            test_url,
            params={},
            response_mode="text",
        )

        assert resp.status == 200

    @pytest.mark.asyncio
    async def test_request_with_none_headers(self, transport, test_url):
        """Test request with None headers."""
        resp = await transport.request(
            "GET",
            test_url,
            headers=None,
            response_mode="text",
        )

        assert resp.status == 200

    def test_cookie_with_no_expires(self, transport):
        """Test cookie without expiration date."""
        cookie = Cookie(
            name="session",
            value="abc123",
            domain="steamcommunity.com",
            path="/",
            expires=None,
        )

        transport.add_cookie(cookie)
        retrieved = transport.get_cookie(URL("https://steamcommunity.com/"), "session")

        assert retrieved is not None
        assert retrieved.expires is None

    def test_cookie_replace_existing(self, transport, steam_login_url):
        """Test that adding a cookie with same name replaces existing."""
        cookie1 = Cookie(name="test", value="value1", domain=steam_login_url.host, path=steam_login_url.path)
        cookie2 = Cookie(name="test", value="value2", domain=steam_login_url.host, path=steam_login_url.path)

        transport.add_cookie(cookie1)
        transport.add_cookie(cookie2)

        retrieved = transport.get_cookie(steam_login_url, "test")
        assert retrieved.value == "value2"
