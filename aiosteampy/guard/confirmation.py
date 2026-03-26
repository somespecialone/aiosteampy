import asyncio
from collections.abc import Awaitable, Iterable
from datetime import datetime
from itertools import batched
from typing import Literal

from ..constants import STEAM_URL, EResult
from ..exceptions import EResultError
from ..id import SteamID
from ..session import SteamSession
from ..transport import Unauthenticated
from .models import Confirmation, ConfirmationType
from .signer import TwoFactorSigner
from .utils import generate_device_id

CONF_URL = STEAM_URL.COMMUNITY / "mobileconf"
GET_ALL_URL = CONF_URL / "getlist"
SEND_URL = CONF_URL / "ajaxop"
SEND_MULTI_URL = CONF_URL / "multiajaxop"

DetailsMode = Literal["none", "listing", "all"]


# no need to check session auth as this component will be used in client
# but to work it require cookie for community
class SteamConfirmations:
    """`Steam` mobile confirmations management."""

    __slots__ = ("_session", "_signer", "_device_id")

    def __init__(self, session: SteamSession, signer: TwoFactorSigner, device_id: str | None = None):
        self._session = session
        self._signer = signer

        self._device_id = generate_device_id(self._session.steam_id.id64) if device_id is None else device_id

    @property
    def signer(self) -> TwoFactorSigner:
        """Crypto signer."""
        return self._signer

    @property
    def device_id(self) -> str:
        """Mobile device id."""
        return self._device_id

    def _create_confirmation_params(self, tag: str) -> dict:
        conf_key, ts = self._signer.gen_confirmation_key(tag=tag)
        return {
            "p": self._device_id,
            "a": self._session.steam_id.id64,
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
        :return: details as string containing html.
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

    async def get_all(self, details: DetailsMode = "none") -> list[Confirmation]:
        """
        Get all standing confirmations.

        .. note:: Details is needed to identify for which ``MarketListing`` conf. belongs.

        :param details: whether to update ``Confirmation`` details.
            Possible values are:
            ``"none"`` - no details will be fetched;
            ``"listing"`` - will update only for ``ConfirmationType.MARKET_LISTING``;
            ``"all"`` - will update for all types.
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

        for chunk in batched(requiring_details, 10):  # concurrently get details with limit
            async with asyncio.TaskGroup() as tg:
                for conf in chunk:
                    tg.create_task(self.get_confirmation_details(conf))

        return confs

    async def get(self, key: str | int, details: DetailsMode = "listing") -> Confirmation | None:
        """
        Get standing ``Confirmation``.

        .. note::
            Details is required to identify for which ``MarketListing`` conf. belongs.
            So ``details`` need to be ``"listing"`` or ``"all"`` if ``key`` is ``MarketListingItem`` ident code.

        :param key: confirmation creator id. Can be a ``MarketListingItem`` ident code,
            ``TradeOffer`` id or, more broad, `request id`.
        :param details: whether to update ``Confirmation`` details.
            Possible values are:
            ``"none"`` - no details will be fetched;
            ``"listing"`` - will update only for ``ConfirmationType.MARKET_LISTING``;
            ``"all"`` - will update for all types.
        :return: ``Confirmation`` or ``None`` if not found.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises RuntimeError: when auth token is invalid or session expired.
        """

        confs = await self.get_all(details)  # unfortunately we need details for all confs. to map to listing
        return next(filter(lambda c: c.creator_id == key or c.listing_item_ident_code == key, confs), None)

    async def send(self, conf: Confirmation, accept: bool = True):
        """
        Perform action with confirmation.

        :param conf: ``Confirmation`` that you want to proceed.
        :param accept: ``True`` if you want to accept confirmation, ``False`` otherwise.
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
        """Accept single confirmation."""
        return self.send(conf, True)

    def deny(self, conf: Confirmation) -> Awaitable[None]:
        """Deny single confirmation."""
        return self.send(conf, False)

    async def send_multiple(self, confs: Iterable[Confirmation], accept: bool = True):
        """
        Perform batch action with multiple confirmations.

        :param confs: iterable with confirmations that you wand to proceed.
        :param accept: ``True`` if you want to accept confirmation, ``False`` otherwise.
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
        :raises RuntimeError: when auth token is invalid or session expired.
        """

        # Is there are limit on confs count?
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
        :raises RuntimeError: when auth token is invalid or session expired.
        """

        confs = await self.get_all()
        confs and await self.deny_multiple(confs)
        return confs
