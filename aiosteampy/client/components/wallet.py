"""Component responsible for `Steam` profile wallet logic."""

from enum import IntEnum
from typing import Awaitable, NamedTuple

from ...constants import SteamURL
from ...exceptions import EResultError, SteamError
from ...session import SteamSession
from ..state import SteamState, WalletInfo


# will be here until needed elsewhere
class EPurchaseResult(IntEnum):
    NO_DETAIL = 0
    AVSFAILURE = 1
    INSUFFICIENT_FUNDS = 2
    CONTACT_SUPPORT = 3
    TIMEOUT = 4
    INVALID_PACKAGE = 5
    INVALID_PAYMENT_METHOD = 6
    INVALID_DATA = 7
    OTHERS_IN_PROGRESS = 8
    ALREADY_PURCHASED = 9
    WRONG_PRICE = 10
    FRAUD_CHECK_FAILED = 11
    CANCELLED_BY_USER = 12
    RESTRICTED_COUNTRY = 13
    BAD_ACTIVATION_CODE = 14
    DUPLICATE_ACTIVATION_CODE = 15
    USE_OTHER_PAYMENT_METHOD = 16
    USE_OTHER_FUNCTION_SOURCE = 17
    INVALID_SHIPPING_ADDRESS = 18
    REGION_NOT_SUPPORTED = 19
    ACCT_IS_BLOCKED = 20
    ACCT_NOT_VERIFIED = 21
    INVALID_ACCOUNT = 22
    STORE_BILLING_COUNTRY_MISMATCH = 23
    DOES_NOT_OWN_REQUIRED_APP = 24
    CANCELED_BY_NEW_TRANSACTION = 25
    FORCE_CANCELED_PENDING = 26
    FAIL_CURRENCY_TRANS_PROVIDER = 27
    FAILED_CYBER_CAFE = 28
    NEEDS_PRE_APPROVAL = 29
    PRE_APPROVAL_DENIED = 30
    WALLET_CURRENCY_MISMATCH = 31
    EMAIL_NOT_VALIDATED = 32
    EXPIRED_CARD = 33
    TRANSACTION_EXPIRED = 34
    WOULD_EXCEED_MAX_WALLET = 35
    MUST_LOGIN_PS_3_APP_FOR_PURCHASE = 36
    CANNOT_SHIP_TO_POBOX = 37
    INSUFFICIENT_INVENTORY = 38
    CANNOT_GIFT_SHIPPED_GOODS = 39
    CANNOT_SHIP_INTERNATIONALLY = 40
    BILLING_AGREEMENT_CANCELLED = 41
    INVALID_COUPON = 42
    EXPIRED_COUPON = 43
    ACCOUNT_LOCKED = 44
    OTHER_ABORTABLE_IN_PROGRESS = 45
    EXCEEDED_STEAM_LIMIT = 46
    OVERLAPPING_PACKAGES_IN_CART = 47
    NO_WALLET = 48
    NO_CACHED_PAYMENT_METHOD = 49
    CANNOT_REDEEM_CODE_FROM_CLIENT = 50
    PURCHASE_AMOUNT_NO_SUPPORTED_BY_PROVIDER = 51
    OVERLAPPING_PACKAGES_IN_PENDING_TRANSACTION = 52
    RATE_LIMITED = 53
    OWNS_EXCLUDED_APP = 54
    CREDIT_CARD_BIN_MISMATCHES_TYPE = 55
    CART_VALUE_TOO_HIGH = 56
    BILLING_AGREEMENT_ALREADY_EXISTS = 57
    POSACODE_NOT_ACTIVATED = 58
    CANNOT_SHIP_TO_COUNTRY = 59
    HUNG_TRANSACTION_CANCELLED = 60
    PAYPAL_INTERNAL_ERROR = 61
    UNKNOWN_GLOBAL_COLLECT_ERROR = 62
    INVALID_TAX_ADDRESS = 63
    PHYSICAL_PRODUCT_LIMIT_EXCEEDED = 64
    PURCHASE_CANNOT_BE_REPLAYED = 65
    DELAYED_COMPLETION = 66
    BUNDLE_TYPE_CANNOT_BE_GIFTED = 67


class RedeemResult(NamedTuple):
    amount: int
    new_balance: str
    """Formatted new wallet balance."""


class WalletComponent:
    """Wallet-related actions."""

    __slots__ = ("_session", "_state")

    def __init__(self, session: SteamSession, state: SteamState):
        self._session = session
        self._state = state

    def get_info(self) -> Awaitable[WalletInfo]:
        """
        Get wallet current user wallet info.

        .. note:: Will update `state` wallet info.

        :return: wallet info.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        return self._state.sync_wallet_info()

    # Will this create wallet?
    async def redeem_code(self, code: str) -> RedeemResult:
        """Redeem `wallet` or `gift` code."""

        store_account_url = SteamURL.STORE / "account"
        r = await self._session.transport.request(
            "POST",
            store_account_url / "ajaxredeemwalletcode/",
            data={"wallet_code": code, "sessionid": self._session.session_id},
            headers={"Origin": str(SteamURL.STORE), "Referer": str(store_account_url / "redeemwalletcode")},
            response_mode="json",
        )

        e_purchase = EPurchaseResult(r.content["detail"])
        if e_purchase is EPurchaseResult.BAD_ACTIVATION_CODE:
            raise SteamError(f"Invalid code: {code}")
        elif e_purchase is EPurchaseResult.DUPLICATE_ACTIVATION_CODE:
            raise SteamError(f"Already redeemed code: {code}")

        try:
            EResultError.check_data(r.content)
        except EResultError as e:
            raise SteamError(f"Failed to redeem code: {code} [{e.result} | {e_purchase}]") from e

        return RedeemResult(int(r.content["amount"]), r.content["formattedNewWalletBalance"])
