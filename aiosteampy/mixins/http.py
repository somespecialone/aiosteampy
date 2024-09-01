from warnings import warn
from inspect import signature

from yarl import URL
from aiohttp import ClientSession, InvalidURL

try:
    from aiohttp_socks import ProxyConnector
except ImportError:
    ProxyConnector = None

from ..constants import STEAM_URL, Language
from ..utils import (
    get_cookie_value_from_session,
    remove_cookie_from_session,
    patch_session_with_http_proxy,
    add_cookie_to_session,
)

SESSION_ID_COOKIE = "sessionid"
LANG_COOKIE = "Steam_Language"
TZ_OFFSET_COOKIE = "timezoneOffset"
COOKIE_URLS = (STEAM_URL.COMMUNITY, STEAM_URL.STORE, STEAM_URL.HELP)


class SteamHTTPTransportMixin:
    """Handler of session instance, proxy, helper cookies getters/setters."""

    # https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/transports/WebApiTransport.ts

    __slots__ = ()

    # required instance attributes
    session: ClientSession  # to use proxy session need to be patched

    @property
    def user_agent(self) -> str | None:
        return self.session.headers.get("User-Agent")

    @user_agent.setter
    def user_agent(self, value: str | None):
        if value is None:
            self.session.headers.pop("User-Agent", None)
        else:
            self.session.headers["User-Agent"] = value

    @property
    def language(self) -> Language:
        """Language of Steam html pages, json info, descriptions, etc."""
        return Language(get_cookie_value_from_session(self.session, STEAM_URL.COMMUNITY, LANG_COOKIE))

    @language.setter
    def language(self, value: Language | None):
        for url in COOKIE_URLS:
            if value is None:
                remove_cookie_from_session(self.session, url, LANG_COOKIE)
            else:
                add_cookie_to_session(self.session, url, LANG_COOKIE, value.value, secure=True)

    @property
    def tz_offset(self) -> str:
        return get_cookie_value_from_session(self.session, STEAM_URL.COMMUNITY, TZ_OFFSET_COOKIE)

    @tz_offset.setter
    def tz_offset(self, value: str | None):
        for url in COOKIE_URLS:
            if value is None:
                remove_cookie_from_session(self.session, url, TZ_OFFSET_COOKIE)
            else:
                add_cookie_to_session(self.session, url, TZ_OFFSET_COOKIE, value, samesite=True)

    # because this cookie set to guests also
    @property
    def session_id(self) -> str | None:
        """`sessionid` cookie value for `Steam Community` domain (https://steamcommunity.com)"""
        return self.get_session_id(STEAM_URL.COMMUNITY)

    @session_id.setter
    def session_id(self, value: str | None):
        self.set_session_id(STEAM_URL.COMMUNITY, value)

    # https://github.com/DoctorMcKay/node-steamcommunity/blob/7c564c1453a5ac413d9312b8cf8fe86e7578b309/index.js#L177
    def get_session_id(self, domain: URL) -> str | None:
        """Get `sessionid` cookie value for `Steam` domain"""

        return get_cookie_value_from_session(self.session, domain, SESSION_ID_COOKIE)

    def set_session_id(self, domain: URL, value: str | None):
        """Set `sessionid` cookie value for `Steam` domain"""

        if value is None:
            remove_cookie_from_session(self.session, domain, SESSION_ID_COOKIE)
        else:
            add_cookie_to_session(self.session, domain, SESSION_ID_COOKIE, value, samesite="None", secure=True)

    @staticmethod
    def _session_helper(session: ClientSession = None, proxy: str = None) -> ClientSession:
        """
        Helper function. Creates new `ClientSession` instance, patch/bound it to proxy if needed.
        Check passed session for `raise_for_status`.
        """

        if proxy and session:
            raise ValueError("You need to handle proxy connection by yourself with predefined session instance")
        elif proxy:
            if "socks" in proxy:
                if ProxyConnector is None:
                    raise TypeError(
                        """
                        To use `socks` type proxies you need `aiohttp_socks` package. 
                        You can do this with `aiosteampy[socks]` or `aiosteampy[all]` dependency install targets.
                        """
                    )

                # let aiohttp_socks parse url by herself
                session = ClientSession(connector=ProxyConnector.from_url(proxy), raise_for_status=True)
            else:  # http/s
                try:
                    proxy = URL(proxy)
                except ValueError as e:
                    raise InvalidURL(proxy) from e

                session = patch_session_with_http_proxy(ClientSession(raise_for_status=True), proxy)

        elif session:
            if not session._raise_for_status:
                warn(
                    "A session instance must be created with `raise_for_status=True` for client to work properly",
                    category=UserWarning,
                )
        else:  # nothing passed
            session = ClientSession(raise_for_status=True)

        return session

    # _proxy attr will be much easier, straight and less error-prone, why I need this?
    @property
    def proxy(self) -> str | None:
        """Proxy url in format `scheme://username:password@host:port` or `scheme://host:port`"""

        if isinstance(self.session.connector, ProxyConnector or int):  # socks, int to avoid TypeError if None
            c: ProxyConnector = self.session.connector

            scheme = str(c._proxy_type.name).lower()
            username = c._proxy_username
            password = c._proxy_password
            host = c._proxy_host
            port = c._proxy_port

        else:
            def_arg: URL | None = signature(self.session._request).parameters["proxy"].default  # magic

            if def_arg is None:  # client without proxy
                return None

            scheme = def_arg.scheme
            username = def_arg.user
            password = def_arg.password
            host = def_arg.host
            port = def_arg.port

        if username and password:  # with auth
            return f"{scheme}://{username}:{password}@{host}:{port}"
        else:
            return f"{scheme}://{host}:{port}"
