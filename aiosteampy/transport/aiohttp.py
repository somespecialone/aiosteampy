"""AioHTTP implementation of HTTP transport."""

from http.cookies import BaseCookie, Morsel

from yarl import URL
from aiohttp import ClientSession, JsonPayload, MultipartWriter

from .base import Cookie, TransportResponse, BaseSteamTransport


class AiohttpSteamTransport(BaseSteamTransport):
    __slots__ = ("_session",)

    def __init__(self, proxy: str | URL | None = None):
        connector = None

        if proxy is not None and proxy.startswith("socks"):
            try:
                from aiohttp_socks import ProxyConnector
            except ImportError as e:
                raise ImportError(
                    """
                    To use `socks` type proxies you need `aiohttp_socks` package. 
                    You can install it with `aiosteampy[socks]` dependency install target.
                    """
                ) from e

            connector = ProxyConnector.from_url(proxy)
            proxy = None

        self._session = ClientSession(proxy=proxy, connector=connector)

    @property
    def proxy(self) -> URL | None:
        return URL(self._session._default_proxy) if isinstance(self._session._default_proxy, str) else None

    def get_headers(self):
        return self._session.headers

    def set_headers(self, headers):
        self._session.headers.clear()
        self._session.headers.update(headers)

    def get_header(self, name):
        return self._session.headers.get(name)

    def set_header(self, name, value):
        if value is None:
            self._session.headers.pop(name, None)
        else:
            self._session.headers[name] = value

    def _check_if_cookie_is_host_only(self, m: Morsel) -> bool:
        return (m["domain"], m.key) in self._session.cookie_jar._host_only_cookies

    def get_cookie(self, url, name):
        for m in self._session.cookie_jar:
            if m.key == name and m["domain"] == url.host and m["path"] == url.path:
                return Cookie.from_morsel(m, host_only=self._check_if_cookie_is_host_only(m))

    def add_cookie(self, cookie):
        c = BaseCookie({cookie.name: cookie.value})
        m = c[cookie.name]

        if cookie.host_only:
            response_url = URL("https://" + cookie.domain)  # only host and path will be extracted however
        else:
            response_url = URL()  # update_cookies arg default
            m["domain"] = cookie.domain

        m["path"] = cookie.path
        m["expires"] = cookie.expires
        m["secure"] = cookie.secure
        m["httponly"] = cookie.http_only
        m["samesite"] = cookie.same_site
        m["comment"] = cookie.comment

        self._session.cookie_jar.update_cookies(c, response_url=response_url)

    def remove_cookie(self, url, name):
        self._session.cookie_jar.clear(lambda m: m.key == name and m["domain"] == url.host and m["path"] == url.path)

    def get_cookies(self):
        return [
            Cookie.from_morsel(m, host_only=self._check_if_cookie_is_host_only(m)) for m in self._session.cookie_jar
        ]

    def close(self):
        return self._session.close()

    async def _request(
        self,
        method,
        url,
        *,
        params,
        data,
        json,
        multipart,
        headers,
        redirects,
        response_mode,
    ):
        if multipart is not None:
            data = MultipartWriter("form-data")
            for k, val in multipart.items():
                part = data.append(val)
                part.set_content_disposition("form-data", name=k)

        aiohttp_resp = await self._session.request(
            method,
            url,
            params=params,
            data=data,
            json=json,
            headers=headers,
            allow_redirects=redirects,
            raise_for_status=False,
        )

        if response_mode == "meta":  # body is not needed
            content = None
        elif response_mode == "text":
            content = await aiohttp_resp.text()
        elif response_mode == "json" and "json" in aiohttp_resp.content_type:  # bytes if content-type doesn't match
            content = await aiohttp_resp.json()
        else:  # bytes by default
            content = await aiohttp_resp.read()

        resp = TransportResponse(
            status=aiohttp_resp.status,
            headers={**aiohttp_resp.headers},  # hope there will be no problems with multi headers
            content=content,
            status_message=aiohttp_resp.reason,
        )

        return resp
