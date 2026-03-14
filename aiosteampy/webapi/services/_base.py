from ..client import SteamWebAPIClient


class SteamWebApiServiceBase:
    __slots__ = ()

    def __init__(self, api: SteamWebAPIClient):
        self._api = api

    @property
    def webapi(self) -> SteamWebAPIClient:
        """`Steam Web API` client."""
        return self._api
