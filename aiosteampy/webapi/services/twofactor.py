"""Client for interacting with `ITwoFactorService`."""

import time
from collections.abc import Awaitable

from ...id import SteamID
from ..client import SteamWebAPIClient
from ._base import SteamWebApiServiceBase
from .protobufs import *


class TwoFactorServiceClient(SteamWebApiServiceBase):
    """Two-Factor service client."""

    __slots__ = ()

    SERVICE_NAME = "ITwoFactorService"

    async def query_time(self, sender_time: int | None = None) -> CTwoFactorTimeResponse:
        msg = CTwoFactorTimeRequest(sender_time=sender_time)
        r = await self._call("QueryTime", msg)
        return CTwoFactorTimeResponse.parse(r)

    async def query_status(self, steam_id: SteamID, include_last_usage: bool = True) -> CTwoFactorStatusResponse:
        msg = CTwoFactorStatusRequest(steamid=steam_id.id64, include=ETwoFactorStatusFieldFlag(include_last_usage))
        r = await self._call("QueryStatus", msg)
        return CTwoFactorStatusResponse.parse(r)

    async def add_authenticator(
        self,
        steamid: SteamID,
        authenticator_time: int,
        serial_number: int,
        authenticator_type: int,
        device_identifier: str,
        http_headers: list[str] = (),
        version: int = 1,
    ) -> CTwoFactorAddAuthenticatorResponse:
        msg = CTwoFactorAddAuthenticatorRequest(
            steamid=steamid.id64,
            authenticator_time=authenticator_time,
            serial_number=serial_number,
            authenticator_type=authenticator_type,
            device_identifier=device_identifier,
            http_headers=http_headers,
            version=version,
        )
        r = await self._call("AddAuthenticator", msg)
        return CTwoFactorAddAuthenticatorResponse.parse(r)

    async def finalize_add_authenticator(
        self,
        steamid: SteamID,
        authenticator_code: str,
        authenticator_time: int,
        activation_code: str,
        http_headers: list[str] = (),
        validate_sms_code: bool = False,
    ) -> CTwoFactorFinalizeAddAuthenticatorResponse:
        msg = CTwoFactorFinalizeAddAuthenticatorRequest(
            steamid=steamid.id64,
            authenticator_code=authenticator_code,
            authenticator_time=authenticator_time,
            activation_code=activation_code,
            http_headers=http_headers,
            validate_sms_code=validate_sms_code,
        )
        r = await self._call("FinalizeAddAuthenticator", msg)
        return CTwoFactorFinalizeAddAuthenticatorResponse.parse(r)

    async def remove_authenticator(
        self,
        revocation_code: str,
        revocation_reason: int = 0,
        steamguard_scheme: int = 0,
        remove_all_steamguard_cookies: bool = False,
    ) -> CTwoFactorRemoveAuthenticatorResponse:
        msg = CTwoFactorRemoveAuthenticatorRequest(
            revocation_code=revocation_code,
            revocation_reason=revocation_reason,
            steamguard_scheme=steamguard_scheme,
            remove_all_steamguard_cookies=remove_all_steamguard_cookies,
        )
        r = await self._call("RemoveAuthenticator", msg)
        return CTwoFactorRemoveAuthenticatorResponse.parse(r)

    async def remove_authenticator_via_challenge_start(self) -> CTwoFactorRemoveAuthenticatorViaChallengeStartResponse:
        r = await self._call("RemoveAuthenticatorViaChallengeStart")
        return CTwoFactorRemoveAuthenticatorViaChallengeStartResponse.parse(r)

    async def remove_authenticator_via_challenge_continue(
        self,
        sms_code: str,
        generate_new_token: bool = False,
        version: int = 0,
    ) -> CTwoFactorRemoveAuthenticatorViaChallengeContinueResponse:
        msg = CTwoFactorRemoveAuthenticatorViaChallengeContinueRequest(
            sms_code=sms_code,
            generate_new_token=generate_new_token,
            version=version,
        )
        r = await self._call("RemoveAuthenticatorViaChallengeContinue", msg)
        return CTwoFactorRemoveAuthenticatorViaChallengeContinueResponse.parse(r)
