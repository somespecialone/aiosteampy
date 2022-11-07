from enum import Enum
from dataclasses import dataclass, field
from typing import Literal, TypeAlias


from yarl import URL


class STEAM_URL:
    API = URL("https://api.steampowered.com")
    COMMUNITY = URL("https://steamcommunity.com")
    STORE = URL("https://store.steampowered.com")
    HELP = URL("https://help.steampowered.com")
    INSPECT = URL("steam://rungame/730/76561202255233023")
    STATIC = URL("https://community.akamai.steamstatic.com")


# https://stackoverflow.com/a/54732120/19419998
class Game(Enum):
    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __init__(self, _, context_id):
        self._context_id_ = context_id

    @property
    def context_id(self) -> int:
        return self._context_id_

    @property
    def app_id(self) -> int:
        return self._value_

    CSGO = 730, 2
    DOTA2 = 570, 2
    H1Z1 = 433850, 2
    RUST = 252490, 2
    TF2 = 440, 2
    PUBG = 578080, 2

    STEAM = 753, 6  # not actually a game :)

    def __getitem__(self, item: int) -> int:
        return self._value_ if item == 0 else self._context_id_

    def __iter__(self):  # for unpacking
        return (v for v in (self._value_, self._context_id_))


GameType: TypeAlias = Game | tuple[int, int]


class Currency(Enum):
    # https://partner.steamgames.com/doc/store/pricing/currencies

    USD = 1, "$"  # UnitedStates Dollar
    GBP = 2, "£"  # United Kingdom Pound
    EURO = 3, "€"  # European Union Euro
    CHF = 4  # Swiss Francs
    RUB = 5, "pуб"  # Russian Rouble
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
    UAH = 18, "₴"  # Ukrainian Hryvnia
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

    _symbol_map: dict[str, "Currency"]

    def __new__(cls, *args, **kwargs):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __init__(self, _, symbol: str = None):
        self._symbol_ = symbol

    @property
    def symbol(self) -> str | None:
        return self._symbol_

    @classmethod
    def by_symbol(cls, abbr: str) -> "Currency | None":
        return cls._symbol_map.get(abbr)


Currency._symbol_map = {cur._symbol_: cur for cur in Currency.__members__.values() if cur._symbol_}


class TradeOfferState(Enum):
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


@dataclass(eq=False, slots=True)
class ItemDescription:
    value: str
    type: Literal["html"] = "html"  # just because
    color: str | None = None


@dataclass(eq=False, slots=True)
class ItemTag:
    category: str
    internal_name: str
    localized_category_name: str
    localized_tag_name: str
    color: str | None = None


@dataclass(eq=False, slots=True)
class ItemClass:
    game: GameType

    name: str
    name_color: str
    market_name: str
    market_hash_name: str
    type: str | None

    icon: str
    icon_large: str | None

    tags: tuple[ItemTag, ...]
    descriptions: tuple[ItemDescription, ...]

    commodity: bool  # ?
    tradable: bool
    marketable: bool
    market_tradable_restriction: int | None = None
    market_buy_country_restriction: str | None = None
    market_fee_app: int | None = None
    market_marketable_restriction: int | None = None

    # optional csgo attrs
    d_id: int | None = None

    @property
    def icon_url(self) -> URL:
        return STEAM_URL.STATIC / f"economy/image/{self.icon}/96fx96f"

    @property
    def icon_large_url(self) -> URL | None:
        return (STEAM_URL.STATIC / f"economy/image/{self.icon_large}/330x192") if self.icon_large else None


@dataclass(eq=False, slots=True)
class InventoryItem:
    asset_id: int
    instance_id: int
    class_: ItemClass

    owner_id: int

    inspect_link: URL | None = field(init=False, default=None)  # optimization 🚀

    def __post_init__(self):
        if self.class_.d_id:
            url = STEAM_URL.INSPECT / f"+csgo_econ_action_preview S{self.owner_id}A{self.asset_id}D{self.class_.d_id}"
            self.inspect_link = url


# https://github.com/Gobot1234/steam.py/blob/afaa75047ca124dcd226be14c3df28e4cd4dc899/steam/guard.py#L93
@dataclass(eq=False, slots=True)
class Confirmation:
    id: int
    data_conf_id: int
    data_key: int
    trade_id: int
