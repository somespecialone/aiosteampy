"""Client for interacting with `ITwoFactorService`."""

import time
from collections.abc import Awaitable

from ...exceptions import EResultError
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

    async def query_status(self, steam_id: SteamID, include_last_usage: bool = False) -> CTwoFactorStatusResponse:
        msg = CTwoFactorStatusRequest(steamid=steam_id.id64, include=ETwoFactorStatusFieldFlag(include_last_usage))
        r = await self._call("QueryStatus", msg, auth=True)
        return CTwoFactorStatusResponse.parse(r)

    async def add_authenticator(
        self,
        steamid: SteamID,
        device_identifier: str,
        # https://github.com/dyc3/steamguard-cli/blob/a7b6aaed1729f26c68413e7316ea5fd9a89d34c7/steamguard/src/accountlinker.rs#L58
        version: int = 2,
        authenticator_type: int = 1,
        authenticator_time: int | None = None,
        serial_number: int | None = None,
        http_headers: list[str] | None = None,
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
        r = await self._call("AddAuthenticator", msg, auth=True)
        return CTwoFactorAddAuthenticatorResponse.parse(r)

    async def finalize_add_authenticator(
        self,
        steamid: SteamID,
        authenticator_code: str,
        activation_code: str,
        authenticator_time: int | None = None,
        validate_sms_code: bool = False,
        http_headers: list[str] | None = None,
    ) -> CTwoFactorFinalizeAddAuthenticatorResponse:
        msg = CTwoFactorFinalizeAddAuthenticatorRequest(
            steamid=steamid.id64,
            authenticator_code=authenticator_code,
            authenticator_time=authenticator_time or int(time.time()),
            activation_code=activation_code,
            http_headers=http_headers,
            validate_sms_code=validate_sms_code,
        )
        r = await self._call("FinalizeAddAuthenticator", msg, auth=True)
        return CTwoFactorFinalizeAddAuthenticatorResponse.parse(r)

    # we return response and exception from methods where
    # response contain valuable data (like statuses) even in case of EResultError
    async def remove_authenticator(
        self,
        revocation_code: str,
        steamguard_scheme: int = 2,
        revocation_reason: int = 1,
        remove_all_steamguard_cookies: bool = False,
    ) -> tuple[CTwoFactorRemoveAuthenticatorResponse, EResultError | None]:
        msg = CTwoFactorRemoveAuthenticatorRequest(
            revocation_code=revocation_code,
            revocation_reason=revocation_reason,
            steamguard_scheme=steamguard_scheme,
            remove_all_steamguard_cookies=remove_all_steamguard_cookies,
        )
        e = None

        try:
            r = await self._call("RemoveAuthenticator", msg, auth=True)
        except EResultError as err:
            e = err
            r = err.data

        return CTwoFactorRemoveAuthenticatorResponse.parse(r), e

    async def remove_authenticator_via_challenge_start(self) -> CTwoFactorRemoveAuthenticatorViaChallengeStartResponse:
        r = await self._call("RemoveAuthenticatorViaChallengeStart", auth=True)
        return CTwoFactorRemoveAuthenticatorViaChallengeStartResponse.parse(r)

    async def remove_authenticator_via_challenge_continue(
        self,
        sms_code: str,
        generate_new_token: bool = False,
        version: int = 2,
    ) -> CTwoFactorRemoveAuthenticatorViaChallengeContinueResponse:
        msg = CTwoFactorRemoveAuthenticatorViaChallengeContinueRequest(
            sms_code=sms_code,
            generate_new_token=generate_new_token,
            version=version,
        )
        r = await self._call("RemoveAuthenticatorViaChallengeContinue", msg, auth=True)
        return CTwoFactorRemoveAuthenticatorViaChallengeContinueResponse.parse(r)
