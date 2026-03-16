"""Client for interacting with `IAuthenticationService`."""

from collections.abc import Awaitable
from typing import Literal

from ...constants import LIB_ID
from ...id import SteamID
from ..client import Platform, SteamWebAPIClient
from ._base import SteamWebApiServiceBase
from .protobufs import *

GuardCodeTypes = Literal["email", "device"]


class AuthenticationServiceClient(SteamWebApiServiceBase):
    """Authentication service client."""

    __slots__ = ("_api",)

    SERVICE_NAME = "IAuthenticationService"

    async def get_password_rsa_public_key(self, account_name: str) -> CAuthenticationGetPasswordRsaPublicKeyResponse:
        msg = CAuthenticationGetPasswordRsaPublicKeyRequest(account_name=account_name)
        r = await self._call("GetPasswordRSAPublicKey", msg, http_method="GET")
        return CAuthenticationGetPasswordRsaPublicKeyResponse.parse(r)

    async def update_auth_session_with_steam_guard_code(
        self,
        client_id: int,
        steam_id: SteamID,
        auth_code: str,
        code_type: GuardCodeTypes,
    ) -> CAuthenticationUpdateAuthSessionWithSteamGuardCodeResponse:
        msg = CAuthenticationUpdateAuthSessionWithSteamGuardCodeRequest(
            client_id=client_id,
            steamid=steam_id.id64,
            code=auth_code,
            code_type=EAuthSessionGuardType.k_EAuthSessionGuardType_DeviceCode
            if code_type == "device"
            else EAuthSessionGuardType.k_EAuthSessionGuardType_EmailCode,
        )
        r = await self._call("UpdateAuthSessionWithSteamGuardCode", msg)
        return CAuthenticationUpdateAuthSessionWithSteamGuardCodeResponse.parse(r)

    async def get_auth_session_info(self, client_id: int) -> CAuthenticationGetAuthSessionInfoResponse:
        msg = CAuthenticationGetAuthSessionInfoRequest(client_id=client_id)
        r = await self._call("GetAuthSessionInfo", msg)
        return CAuthenticationGetAuthSessionInfoResponse.parse(r)

    def update_auth_session_with_mobile_confirmation(
        self,
        version: int,
        client_id: int,
        steam_id: SteamID,
        signature: bytes,
        confirm: bool,
        persistence: bool,
    ) -> Awaitable[None]:
        msg = CAuthenticationUpdateAuthSessionWithMobileConfirmationRequest(
            version=version,
            client_id=client_id,
            steamid=steam_id.id64,
            signature=signature,
            confirm=confirm,
            persistence=ESessionPersistence(int(persistence)),
        )
        return self._call("UpdateAuthSessionWithMobileConfirmation", msg, response_mode="meta")

    def _get_platform_data(self, device_name: str) -> tuple[str, CAuthenticationDeviceDetails]:
        """Get platform data for `Steam` authentication request. Return `website id` and `device details`."""

        if self._api.is_web:
            return "Community", CAuthenticationDeviceDetails(
                device_friendly_name=device_name,
                platform_type=EAuthTokenPlatformType.k_EAuthTokenPlatformType_WebBrowser,
            )
        else:
            return "Mobile", CAuthenticationDeviceDetails(
                device_friendly_name=device_name,
                platform_type=EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp,
                os_type=-500,  # Android Unknown from EOSType,
                gaming_device_type=528,
            )

    async def begin_auth_session_via_credentials(
        self,
        account_name: str,
        encrypted_password: str,
        encryption_timestamp: int,
        persistence: bool,
        device_name: str = LIB_ID,
    ) -> CAuthenticationBeginAuthSessionViaCredentialsResponse:
        website_id, device_details = self._get_platform_data(device_name)
        msg = CAuthenticationBeginAuthSessionViaCredentialsRequest(
            account_name=account_name,
            encrypted_password=encrypted_password,
            encryption_timestamp=encryption_timestamp,
            remember_login=persistence,
            persistence=ESessionPersistence(int(persistence)),
            website_id=website_id,
            device_details=device_details,
            # language=0,
            # qos_level=2,
        )
        r = await self._call("BeginAuthSessionViaCredentials", msg)
        return CAuthenticationBeginAuthSessionViaCredentialsResponse.parse(r)

    async def begin_auth_session_via_qr(
        self,
        device_name: str = LIB_ID,
    ) -> CAuthenticationBeginAuthSessionViaQrResponse:
        _, device_details = self._get_platform_data(device_name)
        msg = CAuthenticationBeginAuthSessionViaQrRequest(device_details=device_details)
        r = await self._call("BeginAuthSessionViaQR", msg)
        return CAuthenticationBeginAuthSessionViaQrResponse.parse(r)

    async def poll_auth_session_status(
        self,
        client_id: int,
        request_id: bytes,
    ) -> CAuthenticationPollAuthSessionStatusResponse:
        msg = CAuthenticationPollAuthSessionStatusRequest(client_id=client_id, request_id=request_id)
        r = await self._call("PollAuthSessionStatus", msg)
        return CAuthenticationPollAuthSessionStatusResponse.parse(r)

    async def generate_access_token_for_app(
        self,
        refresh_token: str,
        steam_id: SteamID,
        renew_refresh_token: bool,
    ) -> CAuthenticationAccessTokenGenerateForAppResponse:
        msg = CAuthenticationAccessTokenGenerateForAppRequest(
            refresh_token=refresh_token,
            steamid=steam_id.id64,
            renewal_type=ETokenRenewalType.k_ETokenRenewalType_Allow
            if renew_refresh_token
            else ETokenRenewalType.k_ETokenRenewalType_None,
        )
        r = await self._call("GenerateAccessTokenForApp", msg)
        return CAuthenticationAccessTokenGenerateForAppResponse.parse(r)

    async def enumerate_tokens(self, include_revoked: bool) -> CAuthenticationRefreshTokenEnumerateResponse:
        msg = CAuthenticationRefreshTokenEnumerateRequest(include_revoked=include_revoked)
        r = await self._call("EnumerateTokens", msg, auth=True)
        return CAuthenticationRefreshTokenEnumerateResponse.parse(r)

    async def get_auth_sessions_for_account(self) -> CAuthenticationGetAuthSessionsForAccountResponse:
        r = await self._call("GetAuthSessionsForAccount", http_method="GET", auth=True)
        return CAuthenticationGetAuthSessionsForAccountResponse.parse(r)

    def revoke_refresh_token(
        self,
        token_id: int,
        steam_id: SteamID,
        signature: bytes,
        revoke_action: EAuthTokenRevokeAction = EAuthTokenRevokeAction.k_EAuthTokenRevokeLogout,
    ) -> Awaitable[None]:
        msg = CAuthenticationRefreshTokenRevokeRequest(
            token_id=token_id,
            steamid=steam_id.id64,
            signature=signature,
            revoke_action=revoke_action,
        )
        return self._call("RevokeRefreshToken", msg, auth=True, response_mode="meta")

    def revoke_token(
        self,
        token: str,
        revoke_action: EAuthTokenRevokeAction = EAuthTokenRevokeAction.k_EAuthTokenRevokeLogout,
    ) -> Awaitable[None]:
        msg = CAuthenticationTokenRevokeRequest(token=token, revoke_action=revoke_action)
        return self._call("RevokeToken", msg, auth=True, response_mode="meta")

    def close(self) -> Awaitable[None]:
        return self._api.close()
