from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import NamedTuple, Self, TypedDict

from ..utils import create_ident_code


class maFileSession(TypedDict):
    SteamID: int  # 64
    AccessToken: str
    RefreshToken: str
    SessionID: str


class maFile(TypedDict):
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
    fully_enrolled: bool
    Session: maFileSession


class ServerTime(NamedTuple):
    server_time: int
    skew_tolerance_seconds: int
    large_time_jink: int
    probe_frequency_seconds: int
    adjusted_time_probe_frequency_seconds: int
    hint_probe_frequency_seconds: int
    sync_timeout: int
    try_again_seconds: int
    max_attempts: int


# https://github.com/DoctorMcKay/node-steamcommunity/blob/master/resources/EConfirmationType.js
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
@dataclass(eq=False, slots=True)
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
