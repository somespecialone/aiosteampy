"""Client for interacting with `IAuthenticationService`."""

from collections.abc import Awaitable
from typing import Literal

from ...constants import LIB_ID
from ..protobufs.auth import *
from ._base import SteamWebApiServiceBase

GuardCodeTypes = Literal["email", "device"]


class AuthenticationServiceClient(SteamWebApiServiceBase):
    """Authentication service client."""

    __slots__ = ()

    SERVICE_NAME = "IAuthenticationService"

    async def get_password_rsa_public_key(self, account_name: str) -> CAuthenticationGetPasswordRsaPublicKeyResponse:
        msg = CAuthenticationGetPasswordRsaPublicKeyRequest(account_name=account_name)
        r = await self._proto("GetPasswordRSAPublicKey", msg, http_method="GET")
        return CAuthenticationGetPasswordRsaPublicKeyResponse.parse(r)

    async def update_auth_session_with_steam_guard_code(
        self,
        client_id: int,
        steamid: int,
        auth_code: str,
        code_type: GuardCodeTypes,
    ) -> CAuthenticationUpdateAuthSessionWithSteamGuardCodeResponse:
        msg = CAuthenticationUpdateAuthSessionWithSteamGuardCodeRequest(
            client_id=client_id,
            steamid=steamid,
            code=auth_code,
            code_type=EAuthSessionGuardType.k_EAuthSessionGuardType_DeviceCode
            if code_type == "device"
            else EAuthSessionGuardType.k_EAuthSessionGuardType_EmailCode,
        )
        r = await self._proto("UpdateAuthSessionWithSteamGuardCode", msg)
        return CAuthenticationUpdateAuthSessionWithSteamGuardCodeResponse.parse(r)

    async def get_auth_session_info(self, client_id: int) -> CAuthenticationGetAuthSessionInfoResponse:
        msg = CAuthenticationGetAuthSessionInfoRequest(client_id=client_id)
        r = await self._proto("GetAuthSessionInfo", msg, auth=True)
        return CAuthenticationGetAuthSessionInfoResponse.parse(r)

    def update_auth_session_with_mobile_confirmation(
        self,
        version: int,
        client_id: int,
        steamid: int,
        signature: bytes,
        confirm: bool = True,
        persistence: bool = True,
    ) -> Awaitable[None]:
        msg = CAuthenticationUpdateAuthSessionWithMobileConfirmationRequest(
            version=version,
            client_id=client_id,
            steamid=steamid,
            signature=signature,
            confirm=confirm,
            persistence=ESessionPersistence(int(persistence)),
        )
        return self._proto("UpdateAuthSessionWithMobileConfirmation", msg, auth=True, response_mode="meta")

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
        persistence: bool = True,
        device_name: str = LIB_ID,
        # https://github.com/dyc3/steamguard-cli/blob/a7b6aaed1729f26c68413e7316ea5fd9a89d34c7/steamguard/src/userlogin.rs#L136
        language: int = 0,
        qos_level: int = 2,
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
            language=language,
            qos_level=qos_level,
        )
        r = await self._proto("BeginAuthSessionViaCredentials", msg)
        return CAuthenticationBeginAuthSessionViaCredentialsResponse.parse(r)

    async def begin_auth_session_via_qr(
        self,
        device_name: str = LIB_ID,
    ) -> CAuthenticationBeginAuthSessionViaQrResponse:
        _, device_details = self._get_platform_data(device_name)
        msg = CAuthenticationBeginAuthSessionViaQrRequest(device_details=device_details)
        r = await self._proto("BeginAuthSessionViaQR", msg)
        return CAuthenticationBeginAuthSessionViaQrResponse.parse(r)

    async def poll_auth_session_status(
        self,
        client_id: int,
        request_id: bytes,
    ) -> CAuthenticationPollAuthSessionStatusResponse:
        msg = CAuthenticationPollAuthSessionStatusRequest(client_id=client_id, request_id=request_id)
        r = await self._proto("PollAuthSessionStatus", msg)
        return CAuthenticationPollAuthSessionStatusResponse.parse(r)

    async def generate_access_token_for_app(
        self,
        refresh_token: str,
        steamid: int,
        renew_refresh_token: bool = False,
    ) -> CAuthenticationAccessTokenGenerateForAppResponse:
        msg = CAuthenticationAccessTokenGenerateForAppRequest(
            refresh_token=refresh_token,
            steamid=steamid,
            renewal_type=ETokenRenewalType(renew_refresh_token),
        )
        r = await self._proto("GenerateAccessTokenForApp", msg)
        return CAuthenticationAccessTokenGenerateForAppResponse.parse(r)

    async def enumerate_tokens(self, include_revoked: bool = False) -> CAuthenticationRefreshTokenEnumerateResponse:
        msg = CAuthenticationRefreshTokenEnumerateRequest(include_revoked=include_revoked)
        r = await self._proto("EnumerateTokens", msg, auth=True)
        return CAuthenticationRefreshTokenEnumerateResponse.parse(r)

    async def get_auth_sessions_for_account(self) -> CAuthenticationGetAuthSessionsForAccountResponse:
        r = await self._proto("GetAuthSessionsForAccount", http_method="GET", auth=True)
        return CAuthenticationGetAuthSessionsForAccountResponse.parse(r)

    def revoke_refresh_token(
        self,
        token_id: int,
        steamid: int,
        signature: bytes,
        revoke_action: EAuthTokenRevokeAction = EAuthTokenRevokeAction.k_EAuthTokenRevokeLogout,
    ) -> Awaitable[None]:
        msg = CAuthenticationRefreshTokenRevokeRequest(
            token_id=token_id,
            steamid=steamid,
            signature=signature,
            revoke_action=revoke_action,
        )
        return self._proto("RevokeRefreshToken", msg, auth=True, response_mode="meta")

    def revoke_token(
        self,
        token: str,
        revoke_action: EAuthTokenRevokeAction = EAuthTokenRevokeAction.k_EAuthTokenRevokeLogout,
    ) -> Awaitable[None]:
        msg = CAuthenticationTokenRevokeRequest(token=token, revoke_action=revoke_action)
        return self._proto("RevokeToken", msg, auth=True, response_mode="meta")
