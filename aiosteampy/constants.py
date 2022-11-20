"""Constants and enums, some types"""

from typing import TypeAlias, ClassVar, Any, TypeVar, Coroutine
from enum import Enum, IntEnum

from yarl import URL

_T = TypeVar("_T")

CORO: TypeAlias = Coroutine[Any, Any, _T]


# https://stackoverflow.com/a/54732120/19419998
class Game(Enum):
    CSGO = 730, 2
    DOTA2 = 570, 2
    H1Z1 = 433850, 2
    RUST = 252490, 2
    TF2 = 440, 2
    PUBG = 578080, 2

    STEAM = 753, 6  # not actually a game :)

    _steam_id_map: ClassVar[dict[int, "Game"]]

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __init__(self, _, context_id):
        self._context_id_ = context_id
        self._args_tuple_ = (self._value_, self._context_id_)

    @property
    def context_id(self) -> int:
        return self._context_id_

    @property
    def app_id(self) -> int:
        return self._value_

    @classmethod
    def by_steam_id(cls, steam_id: int) -> "Game | None":
        return cls._steam_id_map.get(steam_id)

    def __getitem__(self, index: int) -> int:
        return self._args_tuple_[index]

    def __iter__(self):  # for unpacking
        return iter(self._args_tuple_)


Game._steam_id_map = {g.value: g for g in Game.__members__.values()}

GameType: TypeAlias = Game | tuple[int, int]


class Currency(IntEnum):
    """
    Steam currency enum.

    .. seealso:: https://partner.steamgames.com/doc/store/pricing/currencies
    """

    USD = 1  # UnitedStates Dollar
    GBP = 2  # United Kingdom Pound
    EURO = 3  # European Union Euro
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

    _name_map: ClassVar[dict[str, "Currency"]]

    @classmethod
    def by_name(cls, name: str) -> "Currency":
        return cls._name_map[name]


Currency._name_map = {c.name: c for c in Currency.__members__.values()}


class Language(str, Enum):  # like StrEnum from python 3.11
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

    def __str__(self):
        return self.value


# TODO Countries enum


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


# https://github.com/DoctorMcKay/node-steamcommunity/blob/master/resources/EConfirmationType.js
class ConfirmationType(Enum):
    UNKNOWN = 1
    TRADE = 2
    LISTING = 3

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


_API_BASE = URL("https://api.steampowered.com")  # nah


class STEAM_URL:
    COMMUNITY = URL("https://steamcommunity.com")
    STORE = URL("https://store.steampowered.com")
    HELP = URL("https://help.steampowered.com")
    STATIC = URL("https://community.akamai.steamstatic.com")
    # specific
    MARKET = COMMUNITY / "market/"
    TRADE = COMMUNITY / "tradeoffer"

    class API:
        BASE = _API_BASE

        # interfaces
        class IEconService:
            _IBase = _API_BASE / "IEconService"
            _v = "v1"
            GetTradeHistory = _IBase / "GetTradeHistory" / _v
            GetTradeHoldDurations = _IBase / "GetTradeHoldDurations" / _v
            GetTradeOffer = _IBase / "GetTradeOffer" / _v
            GetTradeOffers = _IBase / "GetTradeOffers" / _v
            GetTradeOffersSummary = _IBase / "GetTradeOffersSummary" / _v
            GetTradeStatus = _IBase / "GetTradeStatus" / _v
