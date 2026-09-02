from collections.abc import Awaitable
from typing import ClassVar, Literal, overload

import betterproto2

from ...transport import FormPayload, JsonPayload, Query
from ..client import HttpMethod, SteamWebAPIClient

JsonResponse = Awaitable[JsonPayload]


class SteamWebApiServiceBase:
    __slots__ = ("_api",)

    SERVICE_NAME: ClassVar[str]

    def __init__(self, api: SteamWebAPIClient):
        self._api = api

    @property
    def webapi(self) -> SteamWebAPIClient:
        """`Steam Web API` client."""
        return self._api

    @overload
    def _proto(  # type: ignore
        self,
        method: str,
        msg: betterproto2.Message | bytes = ...,
        version: int = ...,
        http_method: HttpMethod = ...,
        response_mode: Literal["bytes"] = ...,
        auth: bool = ...,
    ) -> Awaitable[bytes]: ...

    @overload
    def _proto(
        self,
        method: str,
        msg: betterproto2.Message | bytes = ...,
        version: int = ...,
        http_method: HttpMethod = ...,
        response_mode: Literal["meta"] = ...,
        auth: bool = ...,
    ) -> Awaitable[None]: ...

    # Can't type return proto message :(
    def _proto(
        self,
        method: str,
        msg: betterproto2.Message | bytes = b"",  # need to send empty msg to receive response
        version: int = 1,
        http_method: HttpMethod = "POST",
        response_mode: Literal["meta", "bytes"] = "bytes",
        auth: bool = False,
    ) -> Awaitable[bytes | None]:
        """Call webapi method with protobuf message."""
        return self._api.call(
            self.SERVICE_NAME,
            method,
            version,
            http_method,
            protobuf=msg,
            response_mode=response_mode,
            auth=auth,
        )  # type: ignore

    def _urlencoded(
        self,
        method: str,
        version: int = 1,
        params: Query | None = None,
        data: FormPayload | None = None,
        http_method: HttpMethod = "GET",
        response_mode: Literal["meta", "json"] = "json",
        auth=False,
    ) -> JsonResponse:  # presumably dict is always returned
        """Call webapi method with urlencoded data."""
        return self._api.call(
            self.SERVICE_NAME,
            method,
            version,
            http_method,
            urlencoded=data,
            params=params,
            response_mode=response_mode,
            auth=auth,
        )  # type: ignore
