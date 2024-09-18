from typing import overload, Literal
from json import loads
from re import compile
from datetime import datetime

from ..constants import STEAM_URL, ConfirmationType, AppContext, CORO, EResult
from ..exceptions import EResultError, SessionExpired
from ..models import Confirmation, MyMarketListing, EconItem, TradeOffer
from ..utils import create_ident_code
from .login import LoginMixin


CONF_URL = STEAM_URL.COMMUNITY / "mobileconf"
ITEM_INFO_RE = compile(r"'confiteminfo', (?P<item_info>.+), UserYou")
CONF_OP_TAGS = Literal["allow", "cancel"]


class ConfirmationMixin(LoginMixin):
    """
    Mixin with confirmations related methods. Requires `_identity_secret` to be set.
    Depends on `LoginMixin`.
    """

    __slots__ = ()

    @overload
    async def confirm_sell_listing(self, obj: int, app_context: AppContext) -> Confirmation:
        ...

    @overload
    async def confirm_sell_listing(self, obj: MyMarketListing | EconItem | int) -> Confirmation:
        ...

    async def confirm_sell_listing(
        self,
        obj: MyMarketListing | EconItem | int,
        app_context: AppContext = None,
    ) -> Confirmation:
        """
        Perform sell listing confirmation.
        Pass `game` arg only with asset id.

        :param obj: `MyMarketListing` or `EconItem` that you listed or listing id or asset id
        :param app_context: `Steam` app+context. Required when `obj` is asset id
        :return: `Confirmation`
        """

        update_listings = False  # avoid unnecessary requests
        if isinstance(obj, MyMarketListing):
            key = obj.id
        elif isinstance(obj, EconItem):
            key = obj.id
            update_listings = True
        else:  # int
            if app_context is not None:  # asset id & app
                key = create_ident_code(obj, app_context.context, app_context.app.value)
                update_listings = True
            else:  # listing id
                key = obj

        conf = await self.get_confirmation(key, update_listings=update_listings)
        await self.allow_confirmation(conf)

        return conf

    async def confirm_api_key_request(self, request_id: str) -> Confirmation:
        """Perform api key request confirmation."""

        conf = await self.get_confirmation(request_id)
        await self.allow_confirmation(conf)

        return conf

    async def confirm_trade_offer(self, obj: int | TradeOffer) -> Confirmation:
        """Perform sell trade offer confirmation."""

        conf = await self.get_confirmation(obj.id if isinstance(obj, TradeOffer) else obj)
        await self.allow_confirmation(conf)

        return conf

    async def get_confirmation(self, key: str | int, *, update_listings=True) -> Confirmation:
        """
        Fetch all confirmations from `Steam`, filter and get one.

        :param key: `MarketListingItem` ident code, `TradeOffer` id or request id
        :param update_listings: update confirmation details if its type is listing.
            Needed to map confirmation to listing
        :return: `Confirmation`
        :raises KeyError: when unable to find confirmation by key
        :raises EResultError: for ordinary reasons
        """

        confs = await self.get_confirmations(update_listings=update_listings)
        # not well performant but anyway
        conf = next(filter(lambda c: c.creator_id == key or c.listing_item_ident_code == key, confs), None)
        if conf is None:
            raise KeyError(f"Unable to find confirmation for {key} ident/trade/listing id")

        return conf

    async def allow_all_confirmations(self) -> list[Confirmation]:
        """
        Fetch all confirmations and allow them with single request to `Steam`.

        :return: list of allowed confirmations
        :raises EResultError: for ordinary reasons
        """

        confs = await self.get_confirmations()
        confs and await self.allow_multiple_confirmations(confs)
        return confs

    def allow_confirmation(self, conf: Confirmation) -> CORO[None]:
        """Shorthand for `send_confirmation(conf, 'allow')`."""

        return self.send_confirmation(conf, "allow")

    async def send_confirmation(self, conf: Confirmation, tag: CONF_OP_TAGS):
        """
        Perform confirmation action.

        :param conf: `Confirmation` that you want to proceed
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

    async def send_multiple_confirmations(self, confs: list[Confirmation], tag: CONF_OP_TAGS):
        """
        Perform confirmation action for multiple confs with single request to Steam.

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

    async def get_confirmations(self, *, update_listings=True) -> list[Confirmation]:
        """
        Fetch all confirmations.

        :param update_listings: update confirmation details if its type is listing.
            Needed to map confirmation to listing.
        :return: list of `Confirmation`
        :raises EResultError: for ordinary reasons
        :raises SessionExpired:
        """

        tag = "getlist"
        params = await self._create_confirmation_params(tag)
        r = await self.session.get(CONF_URL / tag, params=params)
        rj: dict = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            # https://github.com/DoctorMcKay/node-steamcommunity/blob/1067d4572ee9d467e8f686951901c51028c5c995/components/confirmations.js#L35
            if rj.get("needauth"):
                raise SessionExpired

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
                if update_listings and conf.type is ConfirmationType.LISTING:
                    # get details so we can find confirmation for listing
                    await self.update_confirmation_with_details(conf)
                confs.append(conf)

        return confs

    async def _create_confirmation_params(self, tag: str) -> dict:
        conf_key, ts = await self._gen_confirmation_key(tag=tag)
        return {
            "p": self.device_id,
            "a": self.steam_id,
            "k": conf_key,
            "t": ts,
            "m": "android",
            "tag": tag,
        }

    async def get_confirmation_details(self, obj: Confirmation | int) -> dict[str, ...]:
        """
        Fetch confirmation details from `Steam`.

        :param obj: `Confirmation` or confirmation id
        :return: dict with details
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

        return loads(ITEM_INFO_RE.search(rj["html"])["item_info"])  # TODO TypedDict

    async def update_confirmation_with_details(self, conf: Confirmation):
        """Get confirmation details and update passed `Confirmation` with them."""

        conf.details = await self.get_confirmation_details(conf)
