"""Client for interacting with `IPhoneService`."""

from collections.abc import Awaitable

from ..protobufs.phone import *
from ._base import SteamWebApiServiceBase


class PhoneServiceClient(SteamWebApiServiceBase):
    """Phone service client."""

    __slots__ = ()

    SERVICE_NAME = "IPhoneService"

    async def confirm_add_phone_to_account(self, steamid: int, stoken: str) -> CPhoneAddPhoneToAccountResponse:
        msg = CPhoneConfirmAddPhoneToAccountRequest(steamid=steamid, stoken=stoken)
        r = await self._proto("ConfirmAddPhoneToAccount", msg)
        return CPhoneAddPhoneToAccountResponse.parse(r)

    async def is_account_waiting_for_email_confirmation(self) -> CPhoneIsAccountWaitingForEmailConfirmationResponse:
        r = await self._proto("IsAccountWaitingForEmailConfirmation", auth=True)
        return CPhoneIsAccountWaitingForEmailConfirmationResponse.parse(r)

    def send_phone_verification_code(self, language: int = 0) -> Awaitable[None]:
        msg = CPhoneSendPhoneVerificationCodeRequest(language=language)
        return self._proto("SendPhoneVerificationCode", msg, response_mode="meta")

    async def set_account_phone_number(
        self,
        phone_number: str,
        phone_country_code: str,
    ) -> CPhoneSetAccountPhoneNumberResponse:
        msg = CPhoneSetAccountPhoneNumberRequest(phone_number=phone_number, phone_country_code=phone_country_code)
        r = await self._proto("SetAccountPhoneNumber", msg, auth=True)
        return CPhoneSetAccountPhoneNumberResponse.parse(r)

    def verify_account_phone_with_code(self, code: str) -> Awaitable[None]:
        msg = CPhoneVerifyAccountPhoneWithCodeRequest(code=code)
        return self._proto("VerifyAccountPhoneWithCode", msg, response_mode="meta")

    async def account_phone_status(self) -> CPhoneAccountPhoneStatusResponse:
        r = await self._proto("AccountPhoneStatus", auth=True)
        return CPhoneAccountPhoneStatusResponse.parse(r)
