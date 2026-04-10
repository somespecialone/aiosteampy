import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import IntEnum
from typing import NotRequired, Self, TypedDict

from ..id import SteamID
from .secrets import IdentitySecret, SharedSecret, TwoFactorSecret

ITEM_INFO_RE = re.compile(r"'confiteminfo', (.+), UserYou")  # lang safe


class MaFileSession(TypedDict):
    SteamID: int  # 64
    AccessToken: str
    RefreshToken: str
    SessionID: str


class MaFile(TypedDict):
    """`Steam Desktop Authenticator` file data."""

    shared_secret: str
    serial_number: str
    revocation_code: str
    uri: str
    server_time: int
    account_name: str
    token_gid: str
    identity_secret: str
    secret_1: str
    status: int
    device_id: str
    phone_number_hint: NotRequired[str]
    confirm_type: NotRequired[int]
    fully_enrolled: bool
    Session: MaFileSession


@dataclass(slots=True)
class SteamGuardAccount:
    """`Steam Guard` data representation."""

    account_name: str
    steam_id: SteamID
    device_id: str

    shared_secret: SharedSecret
    identity_secret: IdentitySecret
    secret_1: TwoFactorSecret

    revocation_code: str

    uri: str
    serial_number: int
    token_gid: str

    finalized: bool
    """Whether represents data of activated (enrolled) `Steam Guard` account."""

    def serialize(self) -> dict:
        """Export account data as `JSON-safe` dict."""

        data = asdict(self)
        data["shared_secret"] = self.shared_secret.serialize()
        data["identity_secret"] = self.identity_secret.serialize()
        data["secret_1"] = self.secret_1.serialize()
        return data

    @classmethod
    def deserialize(cls, serialized: dict) -> Self:
        """Import account data from `JSON-safe` dict."""

        account = cls(**serialized)
        account.steam_id = SteamID(account.steam_id)
        account.shared_secret = SharedSecret(serialized["shared_secret"])
        account.identity_secret = IdentitySecret(serialized["identity_secret"])
        account.secret_1 = TwoFactorSecret(serialized["secret_1"])
        return account

    @classmethod
    def from_mafile(cls, mafile: MaFile) -> Self:
        return cls(
            account_name=mafile["account_name"],
            steam_id=SteamID(mafile["Session"]["SteamID"]),
            device_id=mafile["device_id"],
            shared_secret=SharedSecret(mafile["shared_secret"]),
            identity_secret=IdentitySecret(mafile["identity_secret"]),
            secret_1=TwoFactorSecret(mafile["secret_1"]),
            revocation_code=mafile["revocation_code"],
            uri=mafile["uri"],
            serial_number=int(mafile["serial_number"]),
            token_gid=mafile["token_gid"],
            finalized=mafile.get("fully_enrolled", True),  # for Nebula SDA
        )


# https://github.com/SteamRE/SteamKit/blob/cd995a14075c17f749919ccf91f56edf883d35c0/Resources/SteamLanguage/enums.steamd#L1720
class ConfirmationType(IntEnum):
    UNKNOWN = -1
    """Unknown type that used in special cases. Normally should not be present."""

    INVALID = 0
    TEST = 1
    TRADE = 2
    """Required to confirm trade offer."""
    MARKET_LISTING = 3
    """Required to sell item on market."""
    FEATURE_OPT_OUT = 4
    PHONE_NUMBER_CHANGE = 5
    """Required to remove phone number."""
    ACCOUNT_RECOVERY = 6
    BUILD_CHANGE_REQUEST = 7
    ADD_USER = 8
    REGISTER_API_KEY = 9
    """Required to create a new `Web API` key."""
    INVITE_TO_FAMILY_GROUP = 10
    JOIN_FAMILY_GROUP = 11
    MARKET_PURCHASE = 12
    REQUEST_REFUND = 13

    @classmethod
    def get(cls, v: int) -> Self:
        try:
            return cls(v)
        except ValueError:
            return cls.UNKNOWN


# https://github.com/DoctorMcKay/node-steamcommunity/wiki/CConfirmation
@dataclass(slots=True)
class Confirmation:
    """Representation of confirmation entity."""

    id: int
    """Unique id."""
    nonce: str
    """Unique key."""
    creator_id: int
    """Id of the creator. Can be ``TradeOffer`` or ``MarketListing`` id."""
    creation_time: datetime
    """Server time when was created."""
    type: ConfirmationType

    accept: str
    cancel: str

    icon: str | None
    multi: bool  # ?
    headline: str
    summary: list[str]
    warn: str | None  # ?

    _details: str | None = None
    _ident_code: str | None = None

    @property
    def details(self) -> str | None:
        """String contains HTML details."""
        return self._details

    @details.setter
    def details(self, value: str | None):
        self._details = value

        if self.type is ConfirmationType.MARKET_LISTING and value:
            from ..client.econ import create_ident_code  # will import all client module :(

            data: dict = json.loads(ITEM_INFO_RE.search(value).group(1))
            self._ident_code = create_ident_code(data["id"], data["contextid"], data["appid"])

    @property
    def listing_item_ident_code(self) -> str | None:
        """``MarketListingItem`` ident code."""
        return self._ident_code

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return isinstance(other, Confirmation) and self.id == other.id
