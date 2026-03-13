"""Client for interacting with `IAuthenticationService`."""

from base64 import b64encode
from collections.abc import Awaitable
from enum import Enum, auto
from typing import Literal

from betterproto2 import Message

from ...constants import STEAM_URL
from ...id import SteamID
from ...transport import Cookie, ResponseMode
from ..client import HttpMethod, SteamWebAPIClient
from .protobufs import *

API_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

BROWSER_HEADERS = {
    "Referer": str(STEAM_URL.COMMUNITY) + "/",
    "Origin": str(STEAM_URL.COMMUNITY),
}

GuardCodeTypes = Literal["email", "device"]


class Platform(Enum):
    WEB = auto()
    MOBILE = auto()


class AuthenticationServiceClient:
    __slots__ = ("_api", "_platform")

    def __init__(self, api: SteamWebAPIClient, platform: Platform):
        """
        Authentication service client.

        :param api: client to use for requests.
        :param platform: platform type for which client is being initialized.
        """

        if platform is EAuthTokenPlatformType.k_EAuthTokenPlatformType_SteamClient:
            raise ValueError("Steam Client platform is not supported")

        self._api = api
        self._platform = platform

        if self.is_mobile:  # add mobile app specific user agent and cookie
            self._api.transport.user_agent = "okhttp/4.9.2"
            self._api.transport.add_cookie(Cookie("mobileClientVersion", "777777 3.10.3", STEAM_URL.WEB_API.host))
            self._api.transport.add_cookie(Cookie("mobileClient", "android", STEAM_URL.WEB_API.host))

    @property
    def platform(self) -> Platform:
        return self._platform

    @property
    def is_web(self) -> bool:
        """Whether this client is configured for web platform."""
        return self._platform is Platform.WEB

    @property
    def is_mobile(self) -> bool:
        """Whether this client is configured for mobile platform."""
        return self._platform is Platform.MOBILE

    @property
    def webapi(self) -> SteamWebAPIClient:
        return self._api

    async def _call(
        self,
        http_method: HttpMethod,
        api_method: str,
        protobuf: Message,
        response_mode: ResponseMode = "bytes",
    ) -> bytes:
        """Helper method for making API calls to endpoints that require protobuf."""

        params = None
        multipart = None

        protobuf_data = {"input_protobuf_encoded": b64encode(bytes(protobuf)).decode()}

        if http_method == "GET":
            params = {**(params or {}), **protobuf_data}
            # https://github.com/DoctorMcKay/node-steam-session/blob/3ac0f34fd964b3f886ba18ef4824ac43c942e030/src/transports/WebApiTransport.ts#L48
            if self.is_mobile:
                params["origin"] = "SteamMobile"

        else:  # POST
            multipart = {**(multipart or {}), **protobuf_data}

        headers = {**API_HEADERS}
        if self.is_web:
            headers |= BROWSER_HEADERS

        return await self._api.request(
            http_method,
            "IAuthenticationService/" + api_method,
            params=params,
            multipart=multipart,
            headers=headers,
            response_mode=response_mode,
        )

    async def get_password_rsa_public_key(self, account_name: str) -> CAuthenticationGetPasswordRsaPublicKeyResponse:
        msg = CAuthenticationGetPasswordRsaPublicKeyRequest(account_name=account_name)
        r = await self._call("GET", "GetPasswordRSAPublicKey", msg)
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

        r = await self._call("POST", "UpdateAuthSessionWithSteamGuardCode", msg)
        return CAuthenticationUpdateAuthSessionWithSteamGuardCodeResponse.parse(r)

    async def get_auth_session_info(self, client_id: int) -> CAuthenticationGetAuthSessionInfoResponse:
        msg = CAuthenticationGetAuthSessionInfoRequest(client_id=client_id)
        r = await self._call("POST", "GetAuthSessionInfo", msg)
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
        return self._call("POST", "UpdateAuthSessionWithMobileConfirmation", msg, "meta")

    @staticmethod
    def _device_details_transform(data: dict) -> CAuthenticationDeviceDetails:
        if data["platform_type"] is Platform.WEB:
            platform_type = EAuthTokenPlatformType.k_EAuthTokenPlatformType_WebBrowser
        else:
            platform_type = EAuthTokenPlatformType.k_EAuthTokenPlatformType_MobileApp

        return CAuthenticationDeviceDetails(**{**data, "platform_type": platform_type})

    async def begin_auth_session_via_credentials(
        self,
        account_name: str,
        encrypted_password: str,
        encryption_timestamp: int,
        persistence: bool,
        website_id: str,
        device_details: dict,  # i am too lazy
    ) -> CAuthenticationBeginAuthSessionViaCredentialsResponse:
        msg = CAuthenticationBeginAuthSessionViaCredentialsRequest(
            account_name=account_name,
            encrypted_password=encrypted_password,
            encryption_timestamp=encryption_timestamp,
            remember_login=persistence,
            persistence=ESessionPersistence(int(persistence)),
            website_id=website_id,
            device_details=self._device_details_transform(device_details),
            # language=0,
            # qos_level=2,
        )
        r = await self._call("POST", "BeginAuthSessionViaCredentials", msg)
        return CAuthenticationBeginAuthSessionViaCredentialsResponse.parse(r)

    async def begin_auth_session_via_qr(self, device_details: dict) -> CAuthenticationBeginAuthSessionViaQrResponse:
        msg = CAuthenticationBeginAuthSessionViaQrRequest(device_details=self._device_details_transform(device_details))
        r = await self._call("POST", "BeginAuthSessionViaQR", msg)
        return CAuthenticationBeginAuthSessionViaQrResponse.parse(r)

    async def poll_auth_session_status(
        self,
        client_id: int,
        request_id: bytes,
    ) -> CAuthenticationPollAuthSessionStatusResponse:
        msg = CAuthenticationPollAuthSessionStatusRequest(client_id=client_id, request_id=request_id)
        r = await self._call("POST", "PollAuthSessionStatus", msg)
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
        r = await self._call("POST", "GenerateAccessTokenForApp", msg)
        return CAuthenticationAccessTokenGenerateForAppResponse.parse(r)

    async def enumerate_tokens(self, include_revoked: bool = False) -> dict:
        r: dict = await self._api.request(
            "POST",
            "IAuthenticationService/EnumerateTokens",
            auth=True,
            data={"include_revoked": include_revoked},
        )

        return r["response"]

    async def get_auth_sessions_for_account(self) -> dict:
        r: dict = await self._api.request(
            "GET",
            "IAuthenticationService/GetAuthSessionsForAccount",
            auth=True,
        )

        return r["response"]

    # Are we need auth there?
    def revoke_refresh_token(
        self,
        token_id: int,
        steam_id: SteamID,
        signature: bytes,
        revoke_action: EAuthTokenRevokeAction,
    ) -> Awaitable[None]:
        msg = CAuthenticationRefreshTokenRevokeRequest(
            token_id=token_id,
            steamid=steam_id.id64,
            signature=signature,
            revoke_action=revoke_action,
        )
        return self._call("POST", "RevokeRefreshToken", msg, "meta")

    # and there?
    def revoke_token(self, token: str, revoke_action: EAuthTokenRevokeAction) -> Awaitable[None]:
        msg = CAuthenticationTokenRevokeRequest(token=token, revoke_action=revoke_action)
        return self._call("POST", "RevokeToken", msg, "meta")

    def close(self) -> Awaitable[None]:
        return self._api.close()
