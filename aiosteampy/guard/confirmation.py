import json
import re
from collections.abc import Awaitable, Iterable
from datetime import datetime
from typing import Literal

from ..constants import STEAM_URL, EResult
from ..exceptions import EResultError
from ..id import SteamID
from ..session import SteamSession
from .models import Confirmation, ConfirmationType
from .signer import TwoFactorSigner
from .utils import generate_device_id

CONF_URL = STEAM_URL.COMMUNITY / "mobileconf"
ITEM_INFO_RE = re.compile(r"'confiteminfo', (.+), UserYou")  # lang safe
ConfirmationTags = Literal["allow", "cancel"]


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
    def session(self) -> SteamSession:
        return self._session

    @property
    def signer(self) -> TwoFactorSigner:
        return self._signer

    @property
    def steam_id(self) -> SteamID:
        return self._session.steam_id

    @property
    def device_id(self) -> str:
        return self._device_id

    def _create_confirmation_params(self, tag: str) -> dict:
        conf_key, ts = self._signer.gen_confirmation_key(tag=tag)
        return {
            "p": self._device_id,
            "a": self._session.steam_id.id64,
            "k": conf_key,
            "t": ts,
            "m": "android",  # react
            "tag": tag,
        }

    # TODO type
    # html for other types
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

        params = self._create_confirmation_params(f"details{conf_id}")

        r = await self._session.transport.request(
            "GET",
            CONF_URL / f"details/{conf_id}",
            params=params,
            response_mode="json",
        )
        rj: dict = r.content

        EResultError.check_data(rj)

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
        """

        tag = "getlist"
        params = self._create_confirmation_params(tag)

        r = await self._session.transport.request("GET", CONF_URL / tag, params=params, response_mode="json")
        rj: dict = r.content

        EResultError.check_data(rj)

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

        params = self._create_confirmation_params(tag)
        params |= {"op": tag, "cid": conf.id, "ck": conf.nonce}

        r = await self._session.transport.request("GET", CONF_URL / "ajaxop", params=params, response_mode="json")
        rj: dict = r.content

        EResultError.check_data(rj)

    def allow_confirmation(self, conf: Confirmation) -> Awaitable[None]:
        """Allow single confirmation."""

        return self.send_confirmation(conf, "allow")

    def cancel_confirmation(self, conf: Confirmation) -> Awaitable[None]:
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

        data = self._create_confirmation_params(tag)
        data |= {"op": tag, "cid[]": [conf.id for conf in confs], "ck[]": [conf.nonce for conf in confs]}

        r = await self._session.transport.request("POST", CONF_URL / "multiajaxop", data=data, response_mode="json")
        rj: dict = r.content

        EResultError.check_data(rj)

    def allow_multiple_confirmations(self, confs: Iterable[Confirmation]) -> Awaitable[None]:
        """Allow multiple confirmations."""

        return self.send_multiple_confirmations(confs, "allow")

    def cancel_multiple_confirmations(self, confs: Iterable[Confirmation]) -> Awaitable[None]:
        """Cancel multiple confirmations."""

        return self.send_multiple_confirmations(confs, "cancel")

    async def allow_all_confirmations(self) -> list[Confirmation]:
        """
        Perform action with ``"allow"`` tag for all standing confirmations.
        In other words, **allow all confirmations**.

        :return: list of processed confirmations.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
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
        """

        confs = await self.get_confirmations()
        confs and await self.cancel_multiple_confirmations(confs)
        return confs
