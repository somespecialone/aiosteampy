from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import NotRequired, Self, TypedDict

from ..id import SteamID
from ..session import SteamJWT
from ..utils import create_ident_code


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

    # base64 encoded
    shared_secret: str
    identity_secret: str
    secret_1: str

    revocation_code: str

    uri: str
    serial_number: int
    token_gid: str

    finalized: bool
    """Whether represents data of activated (enrolled) `Steam Guard` account."""

    def to_dict(self) -> dict[str, str]:
        """Export account data as JSON-safe dict."""

        return {
            "account_name": self.account_name,
            "steam_id": str(self.steam_id),
            "device_id": self.device_id,
            "shared_secret": self.shared_secret,
            "identity_secret": self.identity_secret,
            "secret_1": self.secret_1,
            "revocation_code": self.revocation_code,
            "uri": self.uri,
            "serial_number": str(self.serial_number),
            "token_gid": self.token_gid,
            "finalized": self.finalized,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Self:
        """Import account data from JSON-safe dict."""

        data = {**data, "steam_id": SteamID(data["steam_id"]), "serial_number": int(data["serial_number"])}
        return cls(**data)

    # just in case
    @classmethod
    def from_mafile(cls, mafile: MaFile) -> Self:
        cls(
            account_name=mafile["account_name"],
            steam_id=SteamID(mafile["Session"]["SteamID"]),
            device_id=mafile["device_id"],
            shared_secret=mafile["shared_secret"],
            identity_secret=mafile["identity_secret"],
            secret_1=mafile["secret_1"],
            revocation_code=mafile["revocation_code"],
            uri=mafile["uri"],
            serial_number=int(mafile["serial_number"]),
            token_gid=mafile["token_gid"],
            finalized=mafile["fully_enrolled"],
        )


# https://github.com/DoctorMcKay/node-steamcommunity/blob/master/resources/EConfirmationType.js
# TODO docstrings
class ConfirmationType(IntEnum):
    UNKNOWN = 1
    TRADE = 2
    LISTING = 3
    # API_KEY = 4  # Probably
    PURCHASE = 12

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
    nonce: str  # conf key
    creator_id: int  # trade/listing id
    creation_time: datetime

    type: ConfirmationType

    icon: str
    multi: bool  # ?
    headline: str
    summary: str
    warn: str | None  # ?

    details: dict | None = None

    @property
    def listing_item_ident_code(self) -> str | None:
        """``MarketListingItem`` ident code if ``details`` is present."""

        if self.details is not None:
            return create_ident_code(self.details["id"], self.details["contextid"], self.details["appid"])

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return isinstance(other, Confirmation) and self.id == other.id
