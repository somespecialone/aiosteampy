"""Client for interacting with `IPhoneService`."""

import time
from collections.abc import Awaitable

from ...id import SteamID
from ..client import SteamWebAPIClient
from ._base import SteamWebApiServiceBase
from .protobufs import *


class PhoneServiceClient(SteamWebApiServiceBase):
    """Phone service client."""

    __slots__ = ("_api",)

    SERVICE_NAME = "IPhoneService"

    async def confirm_add_phone_to_account(self, steamid: SteamID, stoken: str) -> CPhoneAddPhoneToAccountResponse:
        msg = CPhoneConfirmAddPhoneToAccountRequest(steamid=steamid.id64, stoken=stoken)
        r = await self._call("ConfirmAddPhoneToAccount", msg)
        return CPhoneAddPhoneToAccountResponse.parse(r)

    async def is_account_waiting_for_email_confirmation(self) -> CPhoneIsAccountWaitingForEmailConfirmationResponse:
        r = await self._call("IsAccountWaitingForEmailConfirmation")
        return CPhoneIsAccountWaitingForEmailConfirmationResponse.parse(r)

    def send_phone_verification_code(self, language: int = 0) -> Awaitable[None]:
        msg = CPhoneSendPhoneVerificationCodeRequest(language=language)
        return self._call("SendPhoneVerificationCode", msg)

    async def set_account_phone_number(
        self,
        phone_number: str,
        phone_country_code: str,
    ) -> CPhoneSetAccountPhoneNumberResponse:
        msg = CPhoneSetAccountPhoneNumberRequest(phone_number=phone_number, phone_country_code=phone_country_code)
        r = await self._call("SetAccountPhoneNumber", msg)
        return CPhoneSetAccountPhoneNumberResponse.parse(r)

    def verify_account_phone_with_code(self, code: str) -> Awaitable[None]:
        msg = CPhoneVerifyAccountPhoneWithCodeRequest(code=code)
        return self._call("VerifyAccountPhoneWithCode", msg)
