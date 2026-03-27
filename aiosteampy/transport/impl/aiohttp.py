"""AioHTTP implementation of HTTP transport."""

from http.cookies import BaseCookie, Morsel

from aiohttp import ClientConnectionError, ClientSession, JsonPayload, MultipartWriter
from yarl import URL

from aiosteampy.transport.base import BaseSteamTransport, Cookie, TransportResponse
from aiosteampy.transport.exceptions import NetworkError
from aiosteampy.transport.utils import format_http_date


class AiohttpTransport(BaseSteamTransport):
    __slots__ = ("_session",)

    def __init__(self, proxy, ctx, **session_kwargs):
        connector = None

        if proxy is not None and proxy.startswith("socks"):
            try:
                from aiohttp_socks import ProxyConnector
            except ImportError:
                raise ImportError(
                    "To use `socks` type proxies you need `aiohttp_socks` package. "
                    "You can install it with `aiosteampy[socks]` dependency install target."
                )

            connector = ProxyConnector.from_url(proxy)
            proxy = None

        self._session = ClientSession(proxy=proxy, connector=connector, **session_kwargs)

        if user_agent := ctx.get("user_agent"):
            self.user_agent = user_agent

    @property
    def proxy(self):
        return str(self._session._default_proxy) if self._session._default_proxy else None

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
        m["expires"] = format_http_date(cookie.expires) if cookie.expires is not None else None
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

    def has_cookie(self, url, name):
        key = (url.host, url.path[1:])
        if key in self._session.cookie_jar._cookies:  # avoid creating def morsel
            return name in self._session.cookie_jar._cookies[key]

    def close(self):
        return self._session.close()

    async def _request(self, method, url, *, params, data, json, multipart, headers, redirects, response_mode):
        if multipart is not None:
            data = MultipartWriter("form-data")
            for k, val in multipart.items():
                part = data.append(val)
                part.set_content_disposition("form-data", name=k)

        try:
            r = await self._session.request(
                method,
                url,
                params=params,
                data=data,
                json=json,
                headers=headers,
                allow_redirects=redirects,
                raise_for_status=False,
            )

        except ClientConnectionError as e:
            raise NetworkError from e

        if response_mode == "meta":  # body is not needed
            content = None
        elif response_mode == "text":
            content = await r.text()
        elif response_mode == "json":
            content = await r.json(content_type=None)  # force to parse as json
        else:  # bytes by default
            content = await r.read()

        history = ()
        if redirects:
            history = tuple(
                TransportResponse(
                    url=hr.url,
                    status=hr.status,
                    headers={**hr.headers},
                    reason=hr.reason,
                )
                for hr in r.history
            )

        return TransportResponse(
            url=r.url,
            status=r.status,
            headers={**r.headers},  # hope there will be no problems with multi headers
            content=content,
            reason=r.reason,
            redirects=history,
        )
