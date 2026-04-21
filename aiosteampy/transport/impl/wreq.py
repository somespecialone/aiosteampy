"""``python-wreq`` (ex. ``rnet``) implementation of HTTP transport."""

try:
    import wreq
except ImportError:
    raise ImportError(
        "`wreq` package is not found and can be installed with `aiosteampy[wreq]` dependency install target."
    )

from collections.abc import Mapping
from typing import TYPE_CHECKING, Unpack

from wreq import Client, Emulation, HeaderMap, Method, Multipart, Proxy, SameSite
from wreq import Cookie as WreqCookie
from wreq import Part as MultipartPart
from wreq import Policy as RedirectPolicy
from wreq.exceptions import ConnectionError, ConnectionResetError, ProxyConnectionError, TimeoutError, TlsError

if TYPE_CHECKING:
    from wreq import ClientConfig

from yarl import URL

from ...constants import Platform
from ..base import BaseSteamTransport
from ..cookie import Cookie
from ..exceptions import NetworkError, ProxyError
from ..resp import TransportResponse
from ..types import HttpMethod

HTTP_METHOD_MAP: dict[HttpMethod, Method] = {
    "GET": Method.GET,
    "POST": Method.POST,
    "PUT": Method.PUT,
    "PATCH": Method.PATCH,
    "DELETE": Method.DELETE,
    "HEAD": Method.HEAD,
    "OPTIONS": Method.OPTIONS,
}


class HeadersProxy(Mapping[str, str]):
    __slots__ = ("_hdrs",)

    def __init__(self, headers: HeaderMap):
        self._hdrs = headers

    def __getitem__(self, key):
        if item := self._hdrs.__getitem__(key):
            return item.decode()  # whole proxy only for this

    def __contains__(self, key: str):
        return self._hdrs.__contains__(key)

    def __len__(self):
        return self._hdrs.__len__()

    def __iter__(self):
        return self._hdrs.__iter__()

    def __str__(self):
        return str(self._hdrs)


NO_REDIRECT_POLICY = RedirectPolicy.none()
DEF_REDIRECT_POLICY = RedirectPolicy.limited(20)


class WreqTransport(BaseSteamTransport):
    __slots__ = ("_client", "_proxy")

    def __init__(self, client: Client | None = None, *, proxy=None, ctx=None, **client_kwargs: Unpack["ClientConfig"]):
        if client is not None:
            self._client = client
            return

        if ctx is None:
            ctx = {}

        proxies = None
        if proxy:
            proxies = [Proxy.all(proxy)]

        if emulation := client_kwargs.pop("emulation", None):
            pass
        elif ctx.get("platform", Platform.WEB) is Platform.MOBILE:
            emulation = Emulation.OkHttp4_9
        else:
            emulation = Emulation.Firefox147

        # ignore user agent from ctx
        self._client = Client(
            redirect=DEF_REDIRECT_POLICY,
            emulation=emulation,
            proxies=proxies,
            cookie_store=True,
            **client_kwargs,
        )

        self._proxy = proxy

    @property
    def client(self) -> Client:
        """Underlying ``wreq.Client`` object."""
        return self._client

    @property
    def proxy(self):
        return self._proxy

    @staticmethod
    def _wreq_c_from_c(c: Cookie) -> WreqCookie:
        if c.same_site is None:
            same_site = None
        elif c.same_site == "Lax":
            same_site = SameSite.Lax
        else:
            same_site = SameSite.Strict

        return WreqCookie(
            c.name,
            c.value,
            c.domain,
            c.path,
            expires=c.expires,
            secure=c.secure,
            http_only=c.http_only,
            same_site=same_site,
        )

    @staticmethod
    def _c_from_wreq_c(c: WreqCookie, url: URL | None = None) -> Cookie:
        if c.same_site_lax:
            same_site = "Lax"
        elif c.same_site_strict:
            same_site = "Strict"
        else:
            same_site = None

        if url is not None:
            domain = url.host
            path = url.path
        else:
            domain = c.domain
            path = c.path or "/"

        return Cookie(
            c.name,
            c.value,
            domain,
            path,
            expires=c.expires,
            http_only=c.http_only,
            secure=c.secure,
            same_site=same_site,
        )

    def get_cookie(self, url, name):
        if c := self._client.cookie_jar.get(name, str(url)):
            return self._c_from_wreq_c(c, url)

    def add_cookie(self, cookie):
        self._client.cookie_jar.add(self._wreq_c_from_c(cookie), "https://" + cookie.domain + cookie.path)

    def remove_cookie(self, url, name):
        self._client.cookie_jar.remove(name, str(url))

    def get_cookies(self):
        return tuple(self._c_from_wreq_c(c) for c in self._client.cookie_jar.get_all())

    async def close(self):
        self._client.close()

    async def _request(self, method, url, *, params, data, json, multipart, headers, redirects, response_mode):
        if multipart is not None:
            multipart = Multipart(*(MultipartPart(k, val) for k, val in multipart.items()))

        method = HTTP_METHOD_MAP[method]

        try:
            r = await self._client.request(
                method,
                str(url),
                query=params,
                headers=headers,
                form=data,
                json=json,
                multipart=multipart,
                redirect=None if redirects else NO_REDIRECT_POLICY,
            )

        except ProxyConnectionError as e:
            raise ProxyError from e

        except (ConnectionError, ConnectionResetError, TlsError, TimeoutError) as e:
            raise NetworkError from e

        status_code = r.status.as_int()

        if response_mode == "meta":
            content = None
        else:  # parse/decode body if present regardless of status
            body = await r.bytes()
            if not body:
                content = None
            elif status_code >= 300 or response_mode == "bytes":
                content = body
            elif response_mode == "text":
                content = await r.text()
            else:
                content = await r.json()

        history = ()
        if redirects:
            history = tuple(
                TransportResponse(
                    url=URL(hr.url),
                    status=hr.status,
                    headers=HeadersProxy(hr.headers),
                )
                for hr in r.history
            )

        return TransportResponse(
            url=URL(r.url),
            status=status_code,
            headers=HeadersProxy(r.headers),
            content=content,
            history=history,
        )
