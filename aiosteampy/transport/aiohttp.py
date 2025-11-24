from http.cookies import BaseCookie

from yarl import URL
from aiohttp import ClientSession, JsonPayload, MultipartWriter

from .base import Cookie, TransportResponse, BaseHTTPTransport


class AiohttpTransport(BaseHTTPTransport):
    __slots__ = (*BaseHTTPTransport.SLOTS, "_session")

    def __init__(self, *, proxy=None):
        super().__init__(proxy=proxy)

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

    def get_cookie(self, url, name):
        for m in self._session.cookie_jar:
            if m.key == name and m["domain"] == url.host and m["path"] == url.path:
                return Cookie.from_morsel(
                    m,
                    host_only=(m["domain"], m.key) in self._session.cookie_jar._host_only_cookies,
                )

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
            Cookie.from_morsel(m, host_only=(m["domain"], m.key) in self._session.cookie_jar._host_only_cookies)
            for m in self._session.cookie_jar
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
        follow_redirects,
        return_json,
        return_text,
        return_bytes,
        return_none,
    ):
        if multipart is not None:  # TODO this need to be tested/checked
            data = MultipartWriter("form-data")
            for line, line_val in multipart.items():
                part = data.append(line_val)
                part.set_content_disposition("form-data", name=line)

        aiohttp_resp = await self._session.request(
            method,
            url,
            params=params,
            data=data,
            json=json,
            headers=headers,
            allow_redirects=follow_redirects,
        )

        if return_none:  # return value is not expected
            return

        resp = TransportResponse(
            status=aiohttp_resp.status,
            status_message=aiohttp_resp.reason,
            headers={**aiohttp_resp.headers},  # hope there will be no problems with multi headers
        )

        if return_bytes:
            resp.content = await aiohttp_resp.read()
        elif return_text:
            resp.content = await aiohttp_resp.text()
        elif return_json:
            resp.content = await aiohttp_resp.json()

        return resp
