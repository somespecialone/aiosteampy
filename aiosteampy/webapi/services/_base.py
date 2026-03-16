from collections.abc import Awaitable
from typing import ClassVar, Literal

from betterproto2 import Message

from ..client import HttpMethod, SteamWebAPIClient


class SteamWebApiServiceBase:
    __slots__ = ("_api",)

    SERVICE_NAME: ClassVar[str]

    def __init__(self, api: SteamWebAPIClient):
        self._api = api

    @property
    def webapi(self) -> SteamWebAPIClient:
        """`Steam Web API` client."""
        return self._api

    # Can't type return proto message :(
    def _call(
        self,
        method: str,
        msg: Message | bytes = b"",  # need to send empty msg to receive response
        version: int = 1,
        http_method: HttpMethod = "POST",
        response_mode: Literal["meta", "bytes"] = "bytes",
        auth: bool = False,
    ) -> Awaitable[bytes | None]:
        return self._api.request(
            http_method,
            self.SERVICE_NAME,
            method,
            version,
            protobuf=msg,
            response_mode=response_mode,
            auth=auth,
        )
