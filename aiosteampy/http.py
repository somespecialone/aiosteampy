from aiohttp import ClientSession


__all__ = ("SteamHTTPTransportMixin",)


class SteamHTTPTransportMixin:
    """
    Handler of session instance, helper getters/setters.
    Probably future setup for `web api caller` or something similar

    .. seealso:: https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/transports/WebApiTransport.ts
    """

    __slots__ = ()

    session: ClientSession

    def __init__(self, *args, session: ClientSession = None, user_agent: str = None, **kwargs):
        self.session = session or ClientSession(raise_for_status=True)
        if user_agent:
            self.user_agent = user_agent

        super().__init__(*args, **kwargs)

    @property
    def user_agent(self) -> str | None:
        return self.session.headers.get("User-Agent")

    @user_agent.setter
    def user_agent(self, value: str):
        self.session.headers["User-Agent"] = value
