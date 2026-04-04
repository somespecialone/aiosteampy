"""``AioHTTP`` implementation of HTTP transport."""

from http.cookies import BaseCookie, Morsel
from importlib.metadata import version

from aiohttp import ClientConnectionError, ClientSession, MultipartWriter
from yarl import URL

from ..base import BaseSteamTransport, Cookie, TransportResponse
from ..exceptions import NetworkError
from ..utils import format_http_date, parse_http_date

AIOHTTP_VERSION = version("aiohttp")


class AiohttpTransport(BaseSteamTransport):
    __slots__ = ("_session",)

    def __init__(self, proxy, ctx, **session_kwargs):
        connector = None

        if proxy is not None and proxy.startswith("socks"):
            try:
                from aiohttp_socks import ProxyConnector
            except ImportError:
                raise ImportError(
                    "`aiohttp_socks` package is required to use `socks` type proxies. "
                    "It can be installed with `aiosteampy[socks]` dependency install target."
                )

            connector = ProxyConnector.from_url(proxy)
            proxy = None

        if user_agent := ctx.get("user_agent"):
            headers = {"User-Agent": f"{user_agent}(AioHTTP/{AIOHTTP_VERSION})"}
        else:
            headers = None

        self._session = ClientSession(proxy=proxy, connector=connector, headers=headers, **session_kwargs)

    @property
    def proxy(self):
        return str(self._session._default_proxy) if self._session._default_proxy else None

    @staticmethod
    def _c_from_morsel(m: Morsel) -> Cookie:
        return Cookie(
            name=m.key,
            value=m.value,
            domain=m["domain"],
            path=m["path"],
            expires=parse_http_date(m["expires"]),
            http_only=m["httponly"],
            secure=m["secure"],
            same_site=m["samesite"] if m["samesite"] != "None" else None,
        )

    def get_cookie(self, url, name):
        for m in self._session.cookie_jar:
            if m.key == name and m["domain"] == url.host and m["path"] == url.path:
                return self._c_from_morsel(m)

    def add_cookie(self, cookie):
        c = BaseCookie({cookie.name: cookie.value})
        m = c[cookie.name]

        m["expires"] = format_http_date(cookie.expires) if cookie.expires is not None else None
        m["secure"] = cookie.secure
        m["httponly"] = cookie.http_only
        m["samesite"] = str(cookie.same_site)  # safe way to convert None to "None"

        # let all cookies be host only as it does not matter much
        self._session.cookie_jar.update_cookies(c, response_url=URL("https://" + cookie.domain + cookie.path))

    def remove_cookie(self, url, name):
        self._session.cookie_jar.clear(lambda m: m.key == name and m["domain"] == url.host and m["path"] == url.path)

    def get_cookies(self):
        return tuple(self._c_from_morsel(m) for m in self._session.cookie_jar)

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
                    headers=hr.headers,
                    reason=hr.reason,
                )
                for hr in r.history
            )

        return TransportResponse(
            url=r.url,
            status=r.status,
            headers=r.headers,
            content=content,
            reason=r.reason,
            history=history,
        )
