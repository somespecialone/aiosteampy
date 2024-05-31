from functools import partial

from yarl import URL
from aiohttp import ClientSession, InvalidURL

try:
    from aiohttp_socks import ProxyConnector
except ImportError:
    ProxyConnector = None


__all__ = ("SteamHTTPTransportMixin",)


class SteamHTTPTransportMixin:
    """
    Handler of session instance, helper getters/setters.
    Probably future setup for `web api caller` or something similar

    .. seealso:: https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/transports/WebApiTransport.ts
    """

    __slots__ = ()

    session: ClientSession

    def __init__(self, *args, session: ClientSession = None, proxy: str = None, user_agent: str = None, **kwargs):
        if proxy and session:
            raise ValueError("You need to handle proxy connection by yourself with predefined session instance.")
        elif proxy:
            if "socks" in proxy:
                if ProxyConnector is None:
                    raise TypeError(
                        """
                        To use `socks` type proxies you need `aiohttp_socks` package. 
                        You can do this with `aiosteampy[socks]` dependency install target.
                        """
                    )

                self.session = ClientSession(connector=ProxyConnector.from_url(proxy), raise_for_status=True)
            else:  # http/s
                self.session = ClientSession(raise_for_status=True)

                try:
                    proxy = URL(proxy)
                except ValueError as e:
                    raise InvalidURL(proxy) from e

                self.session._request = partial(self.session._request, proxy=proxy)  # patch session instance

        elif session:
            self.session = session
        else:
            self.session = ClientSession(raise_for_status=True)

        if user_agent:
            self.user_agent = user_agent

        super().__init__(*args, **kwargs)

    @property
    def user_agent(self) -> str | None:
        return self.session.headers.get("User-Agent")

    @user_agent.setter
    def user_agent(self, value: str):
        self.session.headers["User-Agent"] = value
