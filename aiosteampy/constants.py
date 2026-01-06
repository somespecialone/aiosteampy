""""""

from typing import TypeAlias, Any, TypeVar, Coroutine, Mapping, NewType
from enum import Enum, IntEnum, StrEnum

from yarl import URL


class Currency(IntEnum):  # already params serializable
    """
    All `Steam` currencies.

    .. seealso::
        Currently supported currencies: https://partner.steamgames.com/doc/store/pricing/currencies.
    """

    USD = 1
    """United States Dollar."""
    GBP = 2
    """United Kingdom Pound."""
    EUR = 3
    """European Union Euro."""
    CHF = 4
    """Swiss Francs."""
    RUB = 5
    """Russian Rouble."""
    PLN = 6
    """Polish Złoty."""
    BRL = 7
    """Brazilian Reals."""
    JPY = 8
    """Japanese Yen."""
    NOK = 9
    """Norwegian Krone."""
    IDR = 10
    """Indonesian Rupiah."""
    MYR = 11
    """Malaysian Ringgit."""
    PHP = 12
    """Philippine Peso."""
    SGD = 13
    """Singapore Dollar."""
    THB = 14
    """Thai Baht."""
    VND = 15
    """Vietnamese Dong."""
    KRW = 16
    """South Korean Won."""
    TRY = 17
    """Turkish Lira. **Support suspended**."""
    UAH = 18
    """Ukrainian Hryvnia."""
    MXN = 19
    """Mexican Peso."""
    CAD = 20
    """Canadian Dollars."""
    AUD = 21
    """Australian Dollars."""
    NZD = 22
    """New Zealand Dollar."""
    CNY = 23
    """Chinese Renminbi (yuan)."""
    INR = 24
    """Indian Rupee."""
    CLP = 25
    """Chilean Peso."""
    PEN = 26
    """Peruvian Sol."""
    COP = 27
    """Colombian Peso."""
    ZAR = 28
    """South African Rand."""
    HKD = 29
    """Hong Kong Dollar."""
    TWD = 30
    """New Taiwan Dollar."""
    SAR = 31
    """Saudi Riyal."""
    AED = 32
    """United Arab Emirates Dirham."""
    SEK = 33
    """Swedish Krona. **Support suspended**."""
    ARS = 34
    """Argentine Peso. **Support suspended**."""
    ILS = 35
    """Israeli New Shekel."""
    BYN = 36
    """Belarusian Ruble. **Support suspended**."""
    KZT = 37
    """Kazakhstani Tenge."""
    KWD = 38
    """Kuwaiti Dinar."""
    QAR = 39
    """Qatari Riyal."""
    CRC = 40
    """Costa Rican Colón."""
    UYU = 41
    """Uruguayan Peso."""
    BGN = 42
    """Bulgarian Lev. **Support suspended**."""
    HRK = 43
    """Croatian Kuna. **Support suspended**."""
    CZK = 44
    """Czech Koruna. **Support suspended**."""
    DKK = 45
    """Danish Krone. **Support suspended**."""
    HUF = 46
    """Hungarian Forint. **Support suspended**."""
    RON = 47
    """Romanian Leu. **Support suspended**."""


class Language(StrEnum):
    """
    Supported languages by `Steam`.

    .. seealso:: https://partner.steamgames.com/doc/store/localization/languages.
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


# TODO need rework
# Steam domains
class STEAM_URL:
    COMMUNITY = URL("https://steamcommunity.com")
    STORE = URL("https://store.steampowered.com")
    LOGIN = URL("https://login.steampowered.com")
    HELP = URL("https://help.steampowered.com")
    STATIC = URL("https://community.akamai.steamstatic.com")
    CHECKOUT = URL("https://checkout.steampowered.com")
    TV = URL("https://steam.tv/")
    # specific
    TRADE = COMMUNITY / "tradeoffer"  # TODO remove after trade comp


class EResult(IntEnum):
    """
    Possible/known `Steam` result codes.

    .. seealso::
        * https://steamerrors.com.
        * https://github.com/DoctorMcKay/node-steam-session/blob/master/src/enums-steam/EResult.ts.
        * https://github.com/DoctorMcKay/node-steamcommunity/blob/master/resources/EResult.js.
    """

    INVALID = 0  # False
    OK = 1  # True
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
    ACCOUNT_LOGON_DENIED_NO_MAIL = 66
    HARDWARE_NOT_CAPABLE_OF_IPT = 67
    IPT_INIT_ERROR = 68
    PARENTAL_CONTROL_RESTRICTED = 69
    FACEBOOK_QUERY_ERROR = 70
    EXPIRED_LOGIN_AUTH_CODE = 71
    IP_LOGIN_RESTRICTION_FAILED = 72
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
    ACCOUNT_LOGIN_DENIED_NEED_TWO_FACTOR = 85
    ITEM_DELETED = 86
    ACCOUNT_LOGIN_DENIED_THROTTLE = 87
    TWO_FACTOR_CODE_MISMATCH = 88
    TWO_FACTOR_ACTIVATION_CODE_MISMATCH = 89
    ACCOUNT_ASSOCIATED_TO_MULTIPLE_PARTNERS = 90
    NOT_MODIFIED = 91
    NO_MOBILE_DEVICE = 92
    TIME_NOT_SYNCED = 93
    SMS_CODE_FAILED = 94
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
