from typing import TYPE_CHECKING, overload, Literal
from json import loads
from re import compile
from datetime import datetime
from contextlib import suppress

from .models import Confirmation, MyMarketListing, EconItem, TradeOffer, EconItemType
from .constants import STEAM_URL, ConfirmationType, GameType, CORO, EResult
from .exceptions import EResultError
from .decorators import identity_secret_required
from .utils import create_ident_code

if TYPE_CHECKING:
    from .client import SteamCommunityMixin

CONF_URL = STEAM_URL.COMMUNITY / "mobileconf"
ITEM_INFO_RE = compile(r"'confiteminfo', (?P<item_info>.+), UserYou")
CONF_OP_TAGS = Literal["allow", "cancel"]


class ConfirmationMixin:
    """
    Mixin with confirmations related methods.
    Depends on :class:`aiosteampy.guard.SteamGuardMixin`.
    """

    __slots__ = ()

    @overload
    async def confirm_sell_listing(self, obj: int, game: GameType) -> Confirmation:
        ...

    @overload
    async def confirm_sell_listing(self, obj: MyMarketListing | EconItemType | int) -> Confirmation:
        ...

    @identity_secret_required
    async def confirm_sell_listing(
        self,
        obj: MyMarketListing | EconItemType | int,
        game: GameType = None,
    ) -> Confirmation:
        """
        Perform sell listing confirmation.
        Pass `game` arg only with asset id.

        :param obj: `MyMarketListing` or `EconItem` that you listed or listing id or asset id
        :param game: `Game` or tuple with app and context id ints. Required when `obj` is asset id
        :return: `Confirmation`
        """

        _update = False
        if isinstance(obj, MyMarketListing):
            key = obj.id
        elif isinstance(obj, (EconItem, tuple)):
            key = create_ident_code(obj[3], obj[0], obj[1])
            _update = True
        else:  # int
            if game:  # asset id & game
                key = create_ident_code(obj, *game)
                _update = True
            else:  # listing id
                key = obj

        conf = await self.get_confirmation(key, _update=_update)
        await self.allow_confirmation(conf)

        return conf

    @identity_secret_required
    async def confirm_api_key_request(self, request_id: str) -> Confirmation:
        """Perform api key request confirmation."""

        conf = await self.get_confirmation(request_id)
        await self.allow_confirmation(conf)

        return conf

    @identity_secret_required
    async def confirm_trade_offer(self, offer: int | TradeOffer) -> Confirmation:
        """Perform sell trade offer confirmation."""

        conf = await self.get_confirmation(offer.id if isinstance(offer, TradeOffer) else offer)
        await self.allow_confirmation(conf)

        return conf

    async def get_confirmation(self, key: str | int, *, _update=False) -> Confirmation:
        """
        Fetch confirmation from `Steam`.

        :param key:
        :return: `Confirmation`
        :raises KeyError: when unable to find confirmation by key
        :raises EResultError: for ordinary reasons
        """

        confs = await self.get_confirmations(_update=_update)
        conf = None
        with suppress(StopIteration):
            conf = next(filter(lambda c: c.creator_id == key or c._asset_ident_code == key, confs))

        if not confs or not conf:
            raise KeyError(f"Unable to find confirmation for {key} ident/trade/listing id.")

        return conf

    async def allow_all_confirmations(self) -> list[Confirmation]:
        """
        Fetch all confirmations and allow its (which passes `predicate`) with single request to Steam.

        :param predicate: callable with single argument `Confirmation`, must return boolean
        :return: list of allowed confirmations
        :raises EResultError: for ordinary reasons
        """

        confs = await self.get_confirmations()
        confs and await self.allow_multiple_confirmations(confs)
        return confs

    def allow_confirmation(self, conf: Confirmation) -> CORO[None]:
        """Shorthand for `send_confirmation(conf, 'allow')`."""

        return self.send_confirmation(conf, "allow")

    @identity_secret_required
    async def send_confirmation(self: "SteamCommunityMixin", conf: Confirmation, tag: CONF_OP_TAGS):
        """
        Perform confirmation action. Remove passed conf from inner cache.

        :param conf: `Confirmation` that you wand to proceed
        :param tag: string literal of confirmation tag. Can be 'allow' or 'cancel'
        """

        params = await self._create_confirmation_params(tag)
        params |= {"op": tag, "cid": conf.id, "ck": conf.nonce}
        r = await self.session.get(CONF_URL / "ajaxop", params=params)
        rj = await r.json()

        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to perform confirmation action"), success, rj)

    def allow_multiple_confirmations(self, confs: list[Confirmation]) -> CORO[None]:
        """Shorthand for `send_multiple_confirmations(conf, 'allow')`."""

        return self.send_multiple_confirmations(confs, "allow")

    @identity_secret_required
    async def send_multiple_confirmations(
        self: "SteamCommunityMixin",
        confs: list[Confirmation],
        tag: CONF_OP_TAGS,
    ):
        """
        Perform confirmation action for multiple confs with single request to Steam.
        Remove passed conf from inner cache.

        :param confs: list of `Confirmation` that you wand to proceed
        :param tag: string literal of confirmation tag. Can be 'allow' or 'cancel'
        """

        data = await self._create_confirmation_params(tag)
        data |= {"op": tag, "cid[]": [conf.id for conf in confs], "ck[]": [conf.nonce for conf in confs]}
        r = await self.session.post(CONF_URL / "multiajaxop", data=data)
        rj: dict = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to perform action for multiple confirmations"), success, rj)

    @identity_secret_required
    async def get_confirmations(self: "SteamCommunityMixin", *, _update=False) -> list[Confirmation]:
        """
        Fetch all confirmations.

        :return: list of `Confirmation`
        :raises EResultError:
        """

        tag = "getlist"
        params = await self._create_confirmation_params(tag)
        r = await self.session.get(CONF_URL / tag, params=params)
        rj: dict = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to fetch confirmations"), success, rj)

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
                if _update and conf.type is ConfirmationType.LISTING:  # get listing item ident code from details
                    await self._update_confirmation(conf)
                confs.append(conf)

        return confs

    async def _create_confirmation_params(self: "SteamCommunityMixin", tag: str) -> dict:
        conf_key, ts = await self.gen_confirmation_key(tag=tag)
        return {
            "p": self.device_id,
            "a": self.steam_id,
            "k": conf_key,
            "t": ts,
            "m": "android",
            "tag": tag,
        }

    async def get_confirmation_details(self: "SteamCommunityMixin", obj: Confirmation | int) -> dict[str, ...]:
        """
        Fetch confirmation details from `Steam`.

        :param obj: `Confirmation` or confirmation id
        :return: dict
        :raises EResultError: for ordinary reasons
        """

        if isinstance(obj, Confirmation):
            conf_id = obj.id
        else:
            conf_id = obj

        params = await self._create_confirmation_params(f"details{conf_id}")
        r = await self.session.get(CONF_URL / f"details/{conf_id}", params=params)
        rj = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to fetch confirmation details"), success, rj)

        # TODO TypedDict
        data: dict = loads(ITEM_INFO_RE.search(rj["html"])["item_info"])
        return data

    async def _update_confirmation(self: "SteamCommunityMixin", conf: Confirmation):
        """Get confirmation details, map/bind confirmation to newly created sell listing with `ident_code`"""
        data = await self.get_confirmation_details(conf)
        conf._asset_ident_code = create_ident_code(data["id"], data["appid"], data["contextid"])
