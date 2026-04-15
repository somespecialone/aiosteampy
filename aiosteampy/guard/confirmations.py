import asyncio
import json
import re
from collections.abc import Awaitable, Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from itertools import batched
from typing import TYPE_CHECKING, Literal, Self, overload

from ..constants import SteamURL
from ..exceptions import Unauthenticated
from ..session import EResultError, SteamSession
from .signer import TwoFactorSigner
from .utils import generate_device_id

if TYPE_CHECKING:  # separate guard from client
    from ..client.app import AppContext
    from ..client.components.market import UserMarketListing
    from ..client.components.trade import TradeOffer
    from ..client.econ import EconItem

CONF_URL = SteamURL.COMMUNITY / "mobileconf"
GET_ALL_URL = CONF_URL / "getlist"
SEND_URL = CONF_URL / "ajaxop"
SEND_MULTI_URL = CONF_URL / "multiajaxop"

DetailsMode = Literal["none", "listing", "all"]

ITEM_INFO_RE = re.compile(r"'confiteminfo', (.+), UserYou")  # lang safe


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


# no need to check session auth as this component will be used in client
# but to work it require cookie for community
class SteamConfirmations:
    """`Steam` mobile confirmations management."""

    __slots__ = ("_session", "_signer", "_device_id")

    def __init__(self, session: SteamSession, signer: TwoFactorSigner, device_id: str | None = None):
        self._session = session
        self._signer = signer

        self._device_id = generate_device_id() if not device_id else device_id

    @property
    def signer(self) -> TwoFactorSigner:
        """Crypto signer."""
        return self._signer

    @property
    def device_id(self) -> str:
        """Mobile device id."""
        return self._device_id

    def _create_confirmation_params(self, tag: str) -> dict:
        conf_key, ts = self._signer.generate_confirmation_key(tag=tag)
        return {
            "p": self._device_id,
            "a": self._session.steam_id,
            "k": conf_key,
            "t": ts,
            "m": "react",  # or mobile?
            "tag": tag,
        }

    async def get_confirmation_details(self, obj: Confirmation | int) -> str:
        """
        Get details for ``obj``.
        Details will be attached to ``Confirmation`` if passed.

        :param obj: ``Confirmation`` or confirmation id.
        :return: details as string containing HTML.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        if isinstance(obj, Confirmation):
            conf_id = obj.id
        else:
            conf_id = obj

        params = self._create_confirmation_params(f"details{conf_id}")

        r = await self._session.transport.request(
            "GET",
            CONF_URL / f"details/{conf_id}",
            params=params,
            response_mode="json",
        )
        rj: dict = r.content

        EResultError.check_data(rj)

        details = rj["html"]
        if isinstance(obj, Confirmation):
            obj.details = details

        return details

    async def get_all(self, details: DetailsMode = "none", *, concurrency: int = 10) -> list[Confirmation]:
        """
        Get all standing confirmations.

        .. note:: Details is needed to identify for which ``MarketListing`` conf. belongs.

        :param details: whether to update ``Confirmation`` details.
            Possible values are:
            ``"none"`` - no details will be fetched;
            ``"listing"`` - will update only for ``ConfirmationType.MARKET_LISTING``;
            ``"all"`` - will update for all types.
        :param concurrency: count of concurrent requests to get `details`.
        :return: list of ``Confirmation``.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises Unauthenticated: when auth cookies are invalid or expired.
        """

        params = self._create_confirmation_params("getlist")

        r = await self._session.transport.request("GET", GET_ALL_URL, params=params, response_mode="json")
        rj: dict = r.content

        if rj.get("needauth"):
            raise Unauthenticated

        EResultError.check_data(rj)

        confs: list[Confirmation] = []
        requiring_details: list[Confirmation] = []
        for conf_data in rj.get("conf", ()):
            conf_data: dict
            conf = Confirmation(
                id=int(conf_data["id"]),
                nonce=conf_data["nonce"],
                creator_id=int(conf_data["creator_id"]),
                creation_time=datetime.fromtimestamp(conf_data["creation_time"]),
                type=ConfirmationType.get(conf_data["type"]),
                accept=conf_data["accept"],
                cancel=conf_data["cancel"],
                icon=conf_data["icon"],
                multi=conf_data["multi"],
                headline=conf_data["headline"],
                summary=conf_data["summary"],
                warn=conf_data["warn"],
            )

            if conf.type is ConfirmationType.UNKNOWN:
                import warnings

                warnings.warn(
                    f"Unknown confirmation type: {conf.type} for {conf.id}. "
                    "Normally this should never happen. Please report to maintainers",
                    RuntimeWarning,
                )

            if details == "all":
                requiring_details.append(conf)
            elif details == "listing" and conf.type is ConfirmationType.MARKET_LISTING:
                requiring_details.append(conf)

            confs.append(conf)

        for batch in batched(requiring_details, concurrency):  # concurrently get details with limit
            async with asyncio.TaskGroup() as tg:
                for conf in batch:
                    tg.create_task(self.get_confirmation_details(conf))

        return confs

    async def get(self, key: str | int, details: DetailsMode = "listing") -> Confirmation | None:
        """
        Get standing ``Confirmation``.

        .. note::
            Details are required to identify for which ``MarketListing`` conf. belongs.
            So ``details`` need to be ``"listing"`` or ``"all"`` if ``key`` is ``MarketListingItem`` ident code.

        :param key: confirmation creator id. Can be a ``MarketListingItem`` ident code,
            ``TradeOffer`` id or, broader, `request id`.
        :param details: whether to update ``Confirmation`` details.
            Possible values are:
            ``"none"`` - no details will be fetched;
            ``"listing"`` - will update only for ``ConfirmationType.MARKET_LISTING``;
            ``"all"`` - will update for all types.
        :return: ``Confirmation`` or ``None`` if not found.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises RuntimeError: when the auth token is invalid or session expired.
        """

        confs = await self.get_all(details)  # unfortunately we need details for all confs. to map to listing
        return next(filter(lambda c: c.creator_id == key or c.listing_item_ident_code == key, confs), None)

    async def send(self, conf: Confirmation, accept: bool = True):
        """
        Perform action with `confirmation`.

        :param conf: `confirmation` for proceeding.
        :param accept: whether to accept `confirmation`.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        op = "allow" if accept else "cancel"
        params = self._create_confirmation_params(op)
        # mutating is slightly faster than updating with new
        params["op"] = op
        params["cid"] = conf.id
        params["ck"] = conf.nonce

        r = await self._session.transport.request("GET", SEND_URL, params=params, response_mode="json")
        rj: dict = r.content

        EResultError.check_data(rj)

    def accept(self, conf: Confirmation) -> Awaitable[None]:
        """Accept a single confirmation."""
        return self.send(conf, True)

    def deny(self, conf: Confirmation) -> Awaitable[None]:
        """Deny a single confirmation."""
        return self.send(conf, False)

    async def send_multiple(self, confs: Iterable[Confirmation], accept: bool = True):
        """
        Perform a batch action with multiple `confirmations`.

        :param confs: `confirmations` for proceeding.
        :param accept: whether confirmations should be accepted or canceled otherwise.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        tag = "allow" if accept else "cancel"
        data = self._create_confirmation_params(tag)
        data["op"] = tag
        data["cid[]"] = [conf.id for conf in confs]
        data["ck[]"] = [conf.nonce for conf in confs]

        r = await self._session.transport.request("POST", SEND_MULTI_URL, data=data, response_mode="json")
        rj: dict = r.content

        EResultError.check_data(rj)

    def accept_multiple(self, confs: Iterable[Confirmation]) -> Awaitable[None]:
        """Accept multiple confirmations."""
        return self.send_multiple(confs, True)

    def deny_multiple(self, confs: Iterable[Confirmation]) -> Awaitable[None]:
        """Cancel multiple confirmations."""
        return self.send_multiple(confs, False)

    async def accept_all(self) -> list[Confirmation]:
        """
        Perform action with ``"allow"`` tag for all standing confirmations.
        In other words, **allow all confirmations**.

        :return: list of processed confirmations.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises RuntimeError: when the auth token is invalid or session expired.
        """

        # Is there some limit on confs count?
        confs = await self.get_all()
        confs and await self.accept_multiple(confs)
        return confs

    async def deny_all(self) -> list[Confirmation]:
        """
        Perform action with ``"cancel"`` tag for all standing confirmations.
        In other words, **cancel all confirmations**.

        :return: list of processed confirmations.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises RuntimeError: when the auth token is invalid or session expired.
        """

        confs = await self.get_all()
        confs and await self.deny_multiple(confs)
        return confs

    # helper methods for components
    @overload
    async def confirm_sell_listing(self, obj: int, app_ctx: "AppContext") -> Confirmation: ...

    @overload
    async def confirm_sell_listing(self, obj: "UserMarketListing | EconItem | int") -> Confirmation: ...

    async def confirm_sell_listing(
        self,
        obj: "UserMarketListing | EconItem | int",
        app_ctx: "AppContext | None" = None,
    ) -> Confirmation:
        """
        Perform `sell listing` confirmation.

        :param obj: listed ``UserMarketListing``, ``EconItem``, `listing id` or `asset id`.
        :param app_ctx: ``AppContext`` of item. Required when ``obj`` is `asset id`.
        :return: processed ``Confirmation``.
        :raises KeyError: if confirmation is not found.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        from ..client.components.market import UserMarketListing
        from ..client.econ import EconItem, create_ident_code

        details = "none"  # avoid unnecessary requests
        if isinstance(obj, UserMarketListing):
            key = obj.id
        elif isinstance(obj, EconItem):
            key = obj.id
            details = "listing"
        else:  # int and app ctx
            if app_ctx is not None:  # asset id & app context
                key = create_ident_code(obj, app_ctx.context_id, app_ctx.app.id)
                details = "listing"
            else:  # listing id
                key = obj

        if conf := await self.get(key, details=details):
            await self.accept(conf)
            return conf
        raise KeyError(f"No confirmation found for listing: {key}")

    async def confirm_api_key_request(self, req_id: int) -> Confirmation:
        """
        Confirm `Steam Web API` key registration.

        :param req_id: `request id` of registration request.
        :raises KeyError: if confirmation not found.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        if conf := await self.get(req_id):
            await self.accept(conf)
            return conf
        raise KeyError(f"No confirmation found for `Steam Web API` request: {req_id}")

    async def confirm_trade_offer(self, obj: "int | TradeOffer") -> Confirmation:
        """
        Confirm `trade offer` countering or sending.

        :param obj: ``TradeOffer`` or `trade offer id`.
        :raises KeyError: if confirmation is not found.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        trade_offer_id = obj if isinstance(obj, int) else obj.trade_offer_id
        if conf := await self.get(trade_offer_id):
            await self.accept(conf)
            return conf
        raise KeyError(f"No confirmation found for trade offer: {trade_offer_id}")
