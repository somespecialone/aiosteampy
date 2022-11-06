import enum
from collections import namedtuple


class GameOptions:
    _predefined_options = namedtuple("_predefined_options", ["app_id", "context_id"])

    STEAM = _predefined_options("753", "6")
    DOTA2 = _predefined_options("570", "2")
    CS = _predefined_options("730", "2")
    CSGO = CS
    TF2 = _predefined_options("440", "2")
    PUBG = _predefined_options("578080", "2")
    RUST = _predefined_options("252490", "2")

    def __init__(self, app_id: str, context_id: str) -> None:
        self.app_id = app_id
        self.context_id = context_id


class Asset:
    def __init__(self, asset_id: str, game: GameOptions, amount: int = 1) -> None:
        self.asset_id = asset_id
        self.game = game
        self.amount = amount

    def to_dict(self):
        return {
            "appid": int(self.game.app_id),
            "contextid": self.game.context_id,
            "amount": self.amount,
            "assetid": self.asset_id,
        }


class Currency(enum.IntEnum):
    USD = 1
    GBP = 2
    EURO = 3
    CHF = 4
    RUB = 5
    UAH = 18


class TradeOfferState(enum.IntEnum):
    Invalid = 1
    Active = 2
    Accepted = 3
    Countered = 4
    Expired = 5
    Canceled = 6
    Declined = 7
    InvalidItems = 8
    ConfirmationNeed = 9
    CanceledBySecondaryFactor = 10
    StateInEscrow = 11


class SteamUrl:
    API_URL = "https://api.steampowered.com"
    COMMUNITY_URL = "https://steamcommunity.com"
    STORE_URL = "https://store.steampowered.com"

    CONF_URL = "https://steamcommunity.com/mobileconf"


class Endpoints:
    CHAT_LOGIN = SteamUrl.API_URL + "/ISteamWebUserPresenceOAuth/Logon/v1"
    SEND_MESSAGE = SteamUrl.API_URL + "/ISteamWebUserPresenceOAuth/Message/v1"
    CHAT_LOGOUT = SteamUrl.API_URL + "/ISteamWebUserPresenceOAuth/Logoff/v1"
    CHAT_POLL = SteamUrl.API_URL + "/ISteamWebUserPresenceOAuth/Poll/v1"
