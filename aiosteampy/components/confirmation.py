import re
import json

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Literal, Iterable

from ..constants import STEAM_URL, EResult, CORO
from ..utils import create_ident_code
from ..exceptions import SessionExpired, EResultError
from ..transport import BaseSteamTransport

from .guard import SteamGuardComponent


CONF_URL = STEAM_URL.COMMUNITY / "mobileconf"
ITEM_INFO_RE = re.compile(r"'confiteminfo', (.+), UserYou")  # lang safe
ConfirmationTags = Literal["allow", "cancel"]


# https://github.com/DoctorMcKay/node-steamcommunity/blob/master/resources/EConfirmationType.js
class ConfirmationType(IntEnum):
    UNKNOWN = 1
    TRADE = 2
    LISTING = 3
    # API_KEY = 4  # Probably
    PURCHASE = 12

    @classmethod
    def get(cls, v: int) -> "ConfirmationType":
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


class ConfirmationComponent:
    __slots__ = (
        "_transport",
        "_guard",
    )

    def __init__(self, transport: BaseSteamTransport, guard: SteamGuardComponent):
        self._transport = transport
        self._guard = guard

    async def _create_confirmation_params(self, tag: str) -> dict:
        conf_key, ts = await self._guard.gen_confirmation_key(tag=tag)
        return {
            "p": self._guard.device_id,
            "a": self._guard.steam_id.id64,
            "k": conf_key,
            "t": ts,
            "m": "android",
            "tag": tag,
        }

    async def get_confirmation_details(self, obj: Confirmation | int) -> dict[str, ...]:
        """
        Get details for **listing type confirmation**.
        If ``obj`` is ``Confirmation`` then details will be updated.

        :param obj: ``Confirmation`` or confirmation id.
        :return: dict with details.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises ValueError: confirmation type is not listing or details are not available.
        """

        if isinstance(obj, Confirmation):
            conf_id = obj.id
            if obj.type is not ConfirmationType.LISTING:
                # in future we can get details for other conf types
                raise ValueError("Confirmation details are available only for listing confirmations")
        else:
            conf_id = obj

        params = await self._create_confirmation_params(f"details{conf_id}")
        r = await self._transport.request("GET", CONF_URL / f"details/{conf_id}", params=params, response_mode="json")
        rj: dict = r.content

        if (eresult := EResult(rj.get("success", 0))) is not EResult.OK:
            raise EResultError(eresult, rj.get("message", ""))

        details = json.loads(ITEM_INFO_RE.search(rj["html"]).group(1))
        if isinstance(obj, Confirmation):
            obj.details = details

        return details

    async def get_confirmations(self, *, details_for_listing_type: bool = True) -> list[Confirmation]:
        """
        Get all standing confirmations.

        :param details_for_listing_type: update ``Confirmation`` details if it has listing type.
            Required to map ``Confirmation`` to market listing.
        :return: list of ``Confirmation``.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises SessionExpired: current login session is expired.
        """

        tag = "getlist"
        params = await self._create_confirmation_params(tag)

        r = await self._transport.request("GET", CONF_URL / tag, params=params, response_mode="json")
        rj: dict = r.content

        # https://github.com/DoctorMcKay/node-steamcommunity/blob/d3e90f6fd3bea65b1ebc1bdaec754f99dcc8ddb3/components/confirmations.js#L35
        if rj.get("needauth"):
            raise SessionExpired

        if (success := EResult(rj.get("success"))) is not EResult.OK:
            raise EResultError(success, rj.get("message", ""))

        confs = []
        if "conf" in rj:
            for conf_data in rj["conf"]:
                conf = Confirmation(
                    id=int(conf_data["id"]),
                    nonce=conf_data["nonce"],
                    creator_id=int(conf_data["creator_id"]),
                    creation_time=datetime.fromtimestamp(conf_data["creation_time"]),
                    type=ConfirmationType.get(conf_data["type"]),
                    icon=conf_data["icon"],
                    multi=conf_data["multi"],
                    headline=conf_data["headline"],
                    summary=conf_data["summary"][0],
                    warn=conf_data["warn"],
                )

                if details_for_listing_type and conf.type is ConfirmationType.LISTING:
                    await self.get_confirmation_details(conf)  # get details so we can find confirmation for listing

                confs.append(conf)

        return confs

    async def get_confirmation(self, key: str | int, *, details_for_listing_type: bool = True) -> Confirmation | None:
        """
        Get standing ``Confirmation`` by ``MarketListingItem`` ident code,
        trade offer id or, generally, request id.

        :param key: ``MarketListingItem`` ident code, `TradeOffer` id or request id.
        :param details_for_listing_type: update ``Confirmation`` details if it has listing type.
            Required to map ``Confirmation`` to market listing.
        :return: ``Confirmation`` or ``None`` if not found.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises SessionExpired: current login session is expired.
        """

        confs = await self.get_confirmations(details_for_listing_type=details_for_listing_type)
        return next(filter(lambda c: c.creator_id == key or c.listing_item_ident_code == key, confs), None)

    async def send_confirmation(self, conf: Confirmation, tag: ConfirmationTags):
        """
        Perform action with confirmation.

        :param conf: ``Confirmation`` that you want to proceed.
        :param tag: string literal of confirmation tag. Can be ``"allow"`` or ``"cancel"``.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        """

        params = await self._create_confirmation_params(tag)
        params |= {"op": tag, "cid": conf.id, "ck": conf.nonce}
        r = await self._transport.request("GET", CONF_URL / "ajaxop", params=params, response_mode="json")
        rj: dict = r.content

        if (success := EResult(rj.get("success"))) is not EResult.OK:
            raise EResultError(success, rj.get("message", ""))

    def allow_confirmation(self, conf: Confirmation) -> CORO[None]:
        """Allow single confirmation."""

        return self.send_confirmation(conf, "allow")

    def cancel_confirmation(self, conf: Confirmation) -> CORO[None]:
        """Cancel single confirmation."""

        return self.send_confirmation(conf, "cancel")

    async def send_multiple_confirmations(self, confs: Iterable[Confirmation], tag: ConfirmationTags):
        """
        Perform batch action with multiple confirmations.

        :param confs: iterable with confirmations that you wand to proceed.
        :param tag: ``"allow"`` or ``"cancel"`` tag.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        """

        data = await self._create_confirmation_params(tag)
        data |= {"op": tag, "cid[]": [conf.id for conf in confs], "ck[]": [conf.nonce for conf in confs]}
        r = await self._transport.request("POST", CONF_URL / "multiajaxop", data=data, response_mode="json")
        rj: dict = r.content

        if (success := EResult(rj.get("success"))) is not EResult.OK:
            raise EResultError(success, rj.get("message", ""))

    def allow_multiple_confirmations(self, confs: Iterable[Confirmation]) -> CORO[None]:
        """Allow multiple confirmations."""

        return self.send_multiple_confirmations(confs, "allow")

    def cancel_multiple_confirmations(self, confs: Iterable[Confirmation]) -> CORO[None]:
        """Cancel multiple confirmations."""

        return self.send_multiple_confirmations(confs, "cancel")

    async def allow_all_confirmations(self) -> list[Confirmation]:
        """
        Perform action with ``"allow"`` tag for all standing confirmations.
        In other words, **allow all confirmations**.

        :return: list of processed confirmations.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises SessionExpired: current login session is expired.
        """

        # Is there are limit on confs count?
        confs = await self.get_confirmations()
        confs and await self.allow_multiple_confirmations(confs)
        return confs

    async def cancel_all_confirmations(self) -> list[Confirmation]:
        """
        Perform action with ``"cancel"`` tag for all standing confirmations.
        In other words, **cancel all confirmations**.

        :return: list of processed confirmations.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises SessionExpired: current login session is expired.
        """

        confs = await self.get_confirmations()
        confs and await self.cancel_multiple_confirmations(confs)
        return confs
