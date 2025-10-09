"""Constants and enums, some types"""

from sys import version_info
from typing import TypeAlias, Any, TypeVar, Coroutine, Mapping
from enum import Enum, IntEnum

from yarl import URL
from aenum import extend_enum

_T = TypeVar("_T")

CORO: TypeAlias = Coroutine[Any, Any, _T]


if version_info < (3, 11):

    class StrEnum(str, Enum):
        """Enum with possibility to be a query param serializable"""

        # also for params serialization, make `print` to show only value which complicates debugging a little
        def __str__(self):
            return self.value

else:
    from enum import StrEnum


class App(IntEnum):
    """App enum. Add new member, when missing"""

    # predefined
    CS2 = 730
    CSGO = CS2  # alias

    DOTA2 = 570
    H1Z1 = 433850
    RUST = 252490
    TF2 = 440
    PUBG = 578080

    STEAM = 753

    @classmethod
    def extend(cls, name: str, value: int) -> "App":
        return extend_enum(cls, name, value)

    @classmethod
    def _generate_name(cls, value) -> str:
        return f"{cls.__name__}_{value}"

    @classmethod
    def _missing_(cls, value: int):
        return cls.extend(cls._generate_name(value), value)  # add new member when missing

    @property
    def app_id(self) -> int:
        return self.value


class AppContext(Enum):
    """
    Combination of `App` and context (sub-inventory of the app)

    .. seealso:: https://dev.doctormckay.com/topic/332-identifying-steam-items/
    """

    # predefined
    CS2 = App.CS2, 2
    CSGO = CS2  # alias
    CS2_PROTECTED = App.CS2, 16  # trade protection

    DOTA2 = App.DOTA2, 2
    H1Z1 = App.H1Z1, 2
    RUST = App.RUST, 2
    TF2 = App.TF2, 2
    PUBG = App.PUBG, 2

    STEAM_GIFTS = App.STEAM, 1
    STEAM_COMMUNITY = App.STEAM, 6
    STEAM_REWARDS = App.STEAM, 7  # item rewards

    @classmethod
    def extend(cls, name: str, value: tuple[App | int, int]) -> "AppContext":
        # for case when passed app id instead of an App enum, e.g. AppContext((730, 2))
        with_enum = (App(value[0]), value[1])
        return extend_enum(cls, name, with_enum)

    @classmethod
    def _generate_name(cls, value: tuple[App, int]) -> str:
        return f"{cls.__name__}_{value[0]}_{value[1]}"

    @classmethod
    def _missing_(cls, value: tuple[App | int, int]):
        with_enum = (App(value[0]), value[1])
        return cls.extend(cls._generate_name(with_enum), with_enum)

    @property
    def app(self) -> App:
        return self.value[0]

    @property
    def app_id(self) -> int:
        return self.value[0].value

    @property
    def context(self) -> int:
        return self.value[1]


class Currency(IntEnum):  # already params serializable
    """
    Steam currency enum.

    .. seealso:: https://partner.steamgames.com/doc/store/pricing/currencies
    """

    USD = 1  # UnitedStates Dollar
    GBP = 2  # United Kingdom Pound
    # EURO = 3  # European Union Euro
    EUR = 3  # European Union Euro
    CHF = 4  # Swiss Francs
    RUB = 5  # Russian Rouble
    PLN = 6  # Polish Złoty
    BRL = 7  # Brazilian Reals
    JPY = 8  # Japanese Yen
    NOK = 9  # Norwegian Krone
    IDR = 10  # Indonesian Rupiah
    MYR = 11  # Malaysian Ringgit
    PHP = 12  # Philippine Peso
    SGD = 13  # Singapore Dollar
    THB = 14  # Thai Baht
    VND = 15  # Vietnamese Dong
    KRW = 16  # South KoreanWon
    TRY = 17  # Turkish Lira
    UAH = 18  # Ukrainian Hryvnia
    MXN = 19  # Mexican Peso
    CAD = 20  # Canadian Dollars
    AUD = 21  # Australian Dollars
    NZD = 22  # New Zealand Dollar
    CNY = 23  # Chinese Renminbi (yuan)
    INR = 24  # Indian Rupee
    CLP = 25  # Chilean Peso
    PEN = 26  # Peruvian Sol
    COP = 27  # Colombian Peso
    ZAR = 28  # South AfricanRand
    HKD = 29  # Hong KongDollar
    TWD = 30  # New TaiwanDollar
    SAR = 31  # Saudi Riyal
    AED = 32  # United ArabEmirates Dirham
    # SEK = 33  # Swedish Krona
    ARS = 34  # Argentine Peso
    ILS = 35  # Israeli NewShekel
    # BYN = 36  # Belarusian Ruble
    KZT = 37  # Kazakhstani Tenge
    KWD = 38  # Kuwaiti Dinar
    QAR = 39  # Qatari Riyal
    CRC = 40  # Costa Rican Colón
    UYU = 41  # Uruguayan Peso
    # BGN = 42  # Bulgarian Lev
    # HRK = 43  # Croatian Kuna
    # CZK = 44  # Czech Koruna
    # DKK = 45  # Danish Krone
    # HUF = 46  # Hungarian Forint
    # RON = 47  # Romanian Leu


class Language(StrEnum):
    """
    Steam languages.

    .. seealso:: https://partner.steamgames.com/doc/store/localization/languages
    """

    ARABIC = "arabic"
    BULGARIAN = "bulgarian"
    SIMPLIFIED_CHINESE = "schinese"
    TRADITIONAL_CHINESE = "tchinese"
    CZECH = "czech"
    DANISH = "danish"
    DUTCH = "dutch"
    ENGLISH = "english"
    FINNISH = "finnish"
    FRENCH = "french"
    GERMAN = "german"
    GREEK = "greek"
    HUNGARIAN = "hungarian"
    ITALIAN = "italian"
    JAPANESE = "japanese"
    KOREAN = "koreana"
    NORWEGIAN = "norwegian"
    POLISH = "polish"
    PORTUGUESE = "portuguese"
    PORTUGUESE_BRAZIL = "brazilian"
    ROMANIAN = "romanian"
    RUSSIAN = "russian"
    SPANISH = "spanish"
    SPANISH_LATIN_AMERICAN = "latam"
    SWEDISH = "swedish"
    THAI = "thai"
    TURKISH = "turkish"
    UKRAINIAN = "ukrainian"
    VIETNAMESE = "vietnamese"


class TradeOfferStatus(Enum):
    INVALID = 1
    ACTIVE = 2
    ACCEPTED = 3
    COUNTERED = 4
    EXPIRED = 5
    CANCELED = 6
    DECLINED = 7
    INVALID_ITEMS = 8
    CONFIRMATION_NEED = 9
    CANCELED_BY_SECONDARY_FACTOR = 10
    STATE_IN_ESCROW = 11
    TRADE_REVERSED = 12


# https://github.com/DoctorMcKay/node-steamcommunity/blob/master/resources/EConfirmationType.js
class ConfirmationType(Enum):
    UNKNOWN = 1
    TRADE = 2
    LISTING = 3
    API_KEY = 4  # TODO find api key value
    PURCHASE = 12

    @classmethod
    def get(cls, v: int) -> "ConfirmationType":
        try:
            return cls(v)
        except ValueError:
            return cls.UNKNOWN


class MarketListingStatus(Enum):
    NEED_CONFIRMATION = 17
    ACTIVE = 1


class MarketHistoryEventType(Enum):
    LISTING_CREATED = 1
    LISTING_CANCELED = 2
    LISTING_SOLD = 3
    LISTING_PURCHASED = 4


# TODO Maybe I can create class with __getattribute__ and then build url trough magic method calls
_API_BASE = URL("https://api.steampowered.com")  # nah
_v = "v1"


class STEAM_URL:
    COMMUNITY = URL("https://steamcommunity.com")  # use this domain in methods
    STORE = URL("https://store.steampowered.com")
    LOGIN = URL("https://login.steampowered.com")
    HELP = URL("https://help.steampowered.com")
    STATIC = URL("https://community.akamai.steamstatic.com")
    # specific
    MARKET = COMMUNITY / "market/"
    TRADE = COMMUNITY / "tradeoffer"

    class API:
        BASE = _API_BASE

        # interfaces
        class IEconService:
            _Base = _API_BASE / "IEconService"

            GetTradeHistory = _Base / "GetTradeHistory" / _v
            GetTradeHoldDurations = _Base / "GetTradeHoldDurations" / _v
            GetTradeOffer = _Base / "GetTradeOffer" / _v
            GetTradeOffers = _Base / "GetTradeOffers" / _v
            GetTradeOffersSummary = _Base / "GetTradeOffersSummary" / _v
            GetTradeStatus = _Base / "GetTradeStatus" / _v

        class IAuthService:
            _Base = _API_BASE / "IAuthenticationService"

            BeginAuthSessionViaCredentials = _Base / "BeginAuthSessionViaCredentials" / _v
            GetPasswordRSAPublicKey = _Base / "GetPasswordRSAPublicKey" / _v
            UpdateAuthSessionWithSteamGuardCode = _Base / "UpdateAuthSessionWithSteamGuardCode" / _v
            PollAuthSessionStatus = _Base / "PollAuthSessionStatus" / _v
            GenerateAccessTokenForApp = _Base / "GenerateAccessTokenForApp" / _v


T_PARAMS: TypeAlias = Mapping[str, int | str | float]
T_PAYLOAD: TypeAlias = Mapping[str, str | int | float | bool | None | list | Mapping]
T_HEADERS: TypeAlias = Mapping[str, str]


class EnumWithMultipleValues(Enum):
    """Author: ChatGPT"""

    def __new__(cls, *values):
        # The first value is considered the primary value for the enum member
        obj = object.__new__(cls)
        obj._value_ = values[0]
        # Store all the additional values in a class-level dictionary
        if not hasattr(cls, "_alt_map"):
            cls._alt_map = {}
        for value in values:
            cls._alt_map[value] = obj
        return obj

    @classmethod
    def _missing_(cls, value):
        # Handle cases where the value doesn't directly map to a member
        return cls._alt_map.get(value, super()._missing_(value))


# https://github.com/DoctorMcKay/node-steamcommunity/blob/master/resources/EResult.js
class EResult(EnumWithMultipleValues):
    """
    `success` field in response data from Steam.

    .. seealso:: https://steamerrors.com
    """

    UNKNOWN = None  # special case

    INVALID = 0
    OK = 1, True  # due to Steam
    FAIL = 2
    NO_CONNECTION = 3
    INVALID_PASSWORD = 5
    LOGGED_IN_ELSEWHERE = 6
    INVALID_PROTOCOL_VER = 7
    INVALID_PARAM = 8
    FILE_NOT_FOUND = 9
    BUSY = 10
    INVALID_STATE = 11
    INVALID_NAME = 12
    INVALID_EMAIL = 13
    DUPLICATE_NAME = 14
    ACCESS_DENIED = 15
    TIMEOUT = 16
    BANNED = 17
    ACCOUNT_NOT_FOUND = 18
    INVALID_STEAM_ID = 19
    SERVICE_UNAVAILABLE = 20
    NOT_LOGGED_ON = 21
    PENDING = 22
    ENCRYPTION_FAILURE = 23
    INSUFFICIENT_PRIVILEGE = 24
    LIMIT_EXCEEDED = 25
    REVOKED = 26
    EXPIRED = 27
    ALREADY_REDEEMED = 28
    DUPLICATE_REQUEST = 29
    ALREADY_OWNED = 30
    IP_NOT_FOUND = 31
    PERSIST_FAILED = 32
    LOCKING_FAILED = 33
    LOGON_SESSION_REPLACED = 34
    CONNECT_FAILED = 35
    HANDSHAKE_FAILED = 36
    IO_FAILURE = 37
    REMOTE_DISCONNECT = 38
    SHOPPING_CART_NOT_FOUND = 39
    BLOCKED = 40
    IGNORED = 41
    NO_MATCH = 42
    ACCOUNT_DISABLED = 43
    SERVICE_READ_ONLY = 44
    ACCOUNT_NOT_FEATURED = 45
    ADMINISTRATOR_OK = 46
    CONTENT_VERSION = 47
    TRY_ANOTHER_CM = 48
    PASSWORD_REQUIRED_TO_KICK_SESSION = 49
    ALREADY_LOGGED_IN_ELSEWHERE = 50
    SUSPENDED = 51
    CANCELLED = 52
    DATA_CORRUPTION = 53
    DISK_FULL = 54
    REMOTE_CALL_FAILED = 55
    # PASSWORD_NOT_SET= 56 // removed "renamed to PasswordUnset"
    PASSWORD_UNSET = 56
    EXTERNAL_ACCOUNT_UNLINKED = 57
    PSN_TICKET_INVALID = 58
    EXTERNAL_ACCOUNT_ALREADY_LINKED = 59
    REMOTE_FILE_CONFLICT = 60
    ILLEGAL_PASSWORD = 61
    SAME_AS_PREVIOUS_VALUE = 62
    ACCOUNT_LOGON_DENIED = 63
    CANNOT_USE_OLD_PASSWORD = 64
    INVALID_LOGIN_AUTH_CODE = 65
    # ACCOUNT_LOGON_DENIED_NO_MAIL_SENT= 66 // removed "renamed to AccountLogonDeniedNoMail"
    ACCOUNT_LOGON_DENIED_NO_MAIL = 66
    HARDWARE_NOT_CAPABLE_OF_IPT = 67
    IPT_INIT_ERROR = 68
    PARENTAL_CONTROL_RESTRICTED = 69
    FACEBOOK_QUERY_ERROR = 70
    EXPIRED_LOGIN_AUTH_CODE = 71
    IP_LOGIN_RESTRICTION_FAILED = 72
    # ACCOUNT_LOCKED= 73 // removed "renamed to AccountLockedDown"
    ACCOUNT_LOCKED_DOWN = 73
    ACCOUNT_LOGON_DENIED_VERIFIED_EMAIL_REQUIRED = 74
    NO_MATCHING_URL = 75
    BAD_RESPONSE = 76
    REQUIRE_PASSWORD_RE_ENTRY = 77
    VALUE_OUT_OF_RANGE = 78
    UNEXPECTED_ERROR = 79
    DISABLED = 80
    INVALID_CEG_SUBMISSION = 81
    RESTRICTED_DEVICE = 82
    REGION_LOCKED = 83
    RATE_LIMIT_EXCEEDED = 84
    # ACCOUNT_LOGON_DENIED_NEED_TWO_FACTOR_CODE= 85 // removed "renamed to AccountLoginDeniedNeedTwoFactor"
    ACCOUNT_LOGIN_DENIED_NEED_TWO_FACTOR = 85
    # ITEM_OR_ENTRY_HAS_BEEN_DELETED= 86 // removed "renamed to ItemDeleted"
    ITEM_DELETED = 86
    ACCOUNT_LOGIN_DENIED_THROTTLE = 87
    TWO_FACTOR_CODE_MISMATCH = 88
    TWO_FACTOR_ACTIVATION_CODE_MISMATCH = 89
    # ACCOUNT_ASSOCIATED_TO_MULTIPLE_PLAYERS= 90 // removed "renamed to AccountAssociatedToMultiplePartners"
    ACCOUNT_ASSOCIATED_TO_MULTIPLE_PARTNERS = 90
    NOT_MODIFIED = 91
    # NO_MOBILE_DEVICE_AVAILABLE= 92 // removed "renamed to NoMobileDevice"
    NO_MOBILE_DEVICE = 92
    # TIME_IS_OUT_OF_SYNC= 93 // removed "renamed to TimeNotSynced"
    TIME_NOT_SYNCED = 93
    SMS_CODE_FAILED = 94
    # TOO_MANY_ACCOUNTS_ACCESS_THIS_RESOURCE= 95 // removed "renamed to AccountLimitExceeded"
    ACCOUNT_LIMIT_EXCEEDED = 95
    ACCOUNT_ACTIVITY_LIMIT_EXCEEDED = 96
    PHONE_ACTIVITY_LIMIT_EXCEEDED = 97
    REFUND_TO_WALLET = 98
    EMAIL_SEND_FAILURE = 99
    NOT_SETTLED = 100
    NEED_CAPTCHA = 101
    GSLT_DENIED = 102
    GS_OWNER_DENIED = 103
    INVALID_ITEM_TYPE = 104
    IP_BANNED = 105
    GSLT_EXPIRED = 106
    INSUFFICIENT_FUNDS = 107
    TOO_MANY_PENDING = 108
    NO_SITE_LICENSES_FOUND = 109
    WG_NETWORK_SEND_EXCEEDED = 110
    ACCOUNT_NOT_FRIENDS = 111
    LIMITED_USER_ACCOUNT = 112
    CANT_REMOVE_ITEM = 113
    ACCOUNT_HAS_BEEN_DELETED = 114
    ACCOUNT_HAS_AN_EXISTING_USER_CANCELLED_LICENSE = 115
    DENIED_DUE_TO_COMMUNITY_COOLDOWN = 116
    NO_LAUNCHER_SPECIFIED = 117
    MUST_AGREE_TO_SSA = 118
    CLIENT_NO_LONGER_SUPPORTED = 119


TRADABLE_AFTER_DATE_FORMAT = "%b %d, %Y (%H:%M:%S) %Z"
