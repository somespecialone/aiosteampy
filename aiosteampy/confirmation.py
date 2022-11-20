from typing import TYPE_CHECKING, overload, Literal, Callable, TypeAlias
from json import loads
from re import compile
from datetime import datetime

from .models import Confirmation, MyMarketListing, EconItem, TradeOffer, EconItemType
from .constants import STEAM_URL, ConfirmationType, GameType, CORO
from .exceptions import ApiError, ConfirmationError, SessionExpired
from .utils import create_ident_code

if TYPE_CHECKING:
    from .client import SteamClient

__all__ = ("ConfirmationMixin", "CONF_URL")

CONF_URL = STEAM_URL.COMMUNITY / "mobileconf"
ITEM_INFO_RE = compile(r"'confiteminfo', (?P<item_info>.+), UserYou")
CONF_OP_TAGS = Literal["allow", "cancel"]
PRED: TypeAlias = Callable[[Confirmation], bool]


class ConfirmationMixin:
    """
    Mixin with confirmations related methods.
    Depends on :class:`aiosteampy.guard.SteamGuardMixin`.
    """

    __slots__ = ()

    async def remove_confirmation(self, id_or_ident: str | int, conf: Confirmation):
        """
        Remove confirmation silently from cache.

        You can override this method to provide your custom storage.
        """

    async def remove_multiple_confirmations(self, conf_ids: list[int | str], confs: list[Confirmation]):
        """
        Remove multiple confirmations silently from cache.

        You can override this method to provide your custom storage.
        """

        for index, conf_id in enumerate(conf_ids):
            await self.remove_confirmation(conf_id, confs[index])

    async def store_multiple_confirmations(self, conf_ids: list[int | str], confs: list[Confirmation]):
        """
        Cache multiple confirmations to inner store.

        You can override this method to provide your custom storage.
        """

    async def get_confirmation(self, id_or_ident: str | int) -> Confirmation | None:
        """
        Get conf from storage.

        You can override this method to provide your custom storage.
        """

    async def get_confirmations(self, predicate: PRED = None) -> list[Confirmation]:
        """
        Cached confirmations.

        You can override this method to provide your custom storage.
        """

    @overload
    async def confirm_sell_listing(self, obj: int, game: GameType) -> int:
        ...

    @overload
    async def confirm_sell_listing(self, obj: MyMarketListing | EconItemType | int) -> int:
        ...

    async def confirm_sell_listing(self, obj: MyMarketListing | EconItemType | int, game: GameType = None) -> int:
        """
        Perform sell listing confirmation.
        Pass ``game`` arg only with asset id.

        :param obj: `MyMarketListing` or `EconItem` that you listed or listing id or asset id
        :param game: `Game` or tuple with app and context id ints. Required when ``obj`` is asset id
        :return: listing id
        :raises ConfirmationError:
        """

        update = False
        if isinstance(obj, MyMarketListing):
            key = obj.id
        elif isinstance(obj, (EconItem, tuple)):
            key = create_ident_code(obj[3], obj[0], obj[1])
            update = True
        else:  # int
            if game:  # asset id & game
                key = create_ident_code(obj, *game)
                update = True
            else:  # listing id
                key = obj

        conf = await self.get_or_fetch_confirmation(key, update)
        await self.allow_confirmation(conf)

        return conf.creator_id

    async def confirm_trade_offer(self, offer: int | TradeOffer) -> int:
        """
        Perform sell trade offer confirmation.

        :param offer: trade offer id or `TradeOffer`
        :return: trade id
        :raises ConfirmationError:
        """

        conf = await self.get_or_fetch_confirmation(offer.id if isinstance(offer, TradeOffer) else offer)
        await self.allow_confirmation(conf)

        return conf.creator_id

    async def get_or_fetch_confirmation(self, key: str | int, update=False) -> Confirmation:
        conf = await self.get_confirmation(key)
        if not conf:
            confs = await self.fetch_confirmations(
                predicate=lambda c: c.creator_id == key or c.asset_ident_code == key,
                update=update,
            )
            if confs:
                conf = confs[0]
        if not conf:
            raise ConfirmationError(f"Can't find confirmation for {key} ident/trade/listing id.")

        return conf

    async def allow_all_confirmations(self, *, predicate: PRED = None) -> list[Confirmation]:
        """
        Fetch all confirmations and allow its (which passes ``predicate``) with single request to Steam.

        :param predicate: callable with single argument `Confirmation`, must return boolean
        :return: list of allowed confirmations
        :raises ConfirmationError:
        :raises ApiError:
        """

        confs = await self.fetch_confirmations(predicate=predicate)
        confs and await self.allow_multiple_confirmations(confs)
        return confs

    def allow_confirmation(self, conf: Confirmation) -> CORO[None]:
        """Shorthand for "send_confirmation(conf, 'allow')"."""

        return self.send_confirmation(conf, "allow")

    async def send_confirmation(self: "SteamClient", conf: Confirmation, tag: CONF_OP_TAGS) -> None:
        """
        Perform confirmation action. Remove passed conf from inner cache.

        :param conf: `Confirmation` that you wand to proceed
        :param tag: string literal of conf tag. Can be 'allow' or 'cancel'
        :raises ConfirmationError:
        """

        params = await self._create_confirmation_params(tag)
        params |= {"op": tag, "cid": conf.id, "ck": conf.nonce}
        r = await self.session.get(CONF_URL / "ajaxop", params=params)
        rj = await r.json()
        await self.remove_confirmation(conf.asset_ident_code or conf.creator_id, conf)  # delete before raise error

        if not rj.get("success"):
            raise ConfirmationError(
                f"Failed to perform confirmation action `{tag}` for {conf.creator_id} trade/listing id."
            )

    def allow_multiple_confirmations(self, confs: list[Confirmation]) -> CORO[None]:
        """Shorthand for "send_multiple_confirmations(conf, 'allow')"."""

        return self.send_multiple_confirmations(confs, "allow")

    async def send_multiple_confirmations(self: "SteamClient", confs: list[Confirmation], tag: CONF_OP_TAGS) -> None:
        """
        Perform confirmation action for multiple confs with single request to Steam.
        Remove passed conf from inner cache.

        :param confs: list of `Confirmation` that you wand to proceed
        :param tag: string literal of conf tag. Can be 'allow' or 'cancel'
        :raises ConfirmationError:
        """

        data = await self._create_confirmation_params(tag)
        data |= {"op": tag, "cid[]": [conf.id for conf in confs], "ck[]": [conf.nonce for conf in confs]}
        r = await self.session.post(CONF_URL / "multiajaxop", data=data)
        rj: dict[str, ...] = await r.json()
        # delete before raise error
        await self.remove_multiple_confirmations([c.asset_ident_code or c.creator_id for c in confs], confs)

        if not rj.get("success"):
            raise ConfirmationError(f"Failed to perform action `{tag}` for multiple confs.")

    async def fetch_confirmations(
        self: "SteamClient",
        *,
        predicate: PRED = None,
        update=False,
    ) -> list[Confirmation]:
        """
        Fetch confirmations, cache it and return.

        :param predicate: callable with single argument `Confirmation`, must return boolean
        :param update: fetch data and update confirmations.
            Requires to bind newly created sell listing to confirmation.
            You definitely don't need this
        :return: list of `Confirmation`
        :raises ApiError:
        """

        tag = "getlist"
        params = await self._create_confirmation_params(tag)
        r = await self.session.get(CONF_URL / tag, params=params)
        rj: dict[str, ...] = await r.json()
        if not rj.get("success"):
            raise ApiError("Can't fetch confirmations.", rj)

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
                update and conf.type is ConfirmationType.LISTING and await self._update_confirmation(conf)
                confs.append(conf)

        await self.store_multiple_confirmations([c.creator_id for c in confs], confs)
        return [c for c in confs if predicate(c)] if predicate else confs

    async def _create_confirmation_params(self: "SteamClient", tag: str) -> dict[str, ...]:
        conf_key, ts = await self._gen_confirmation_key(tag=tag)
        return {
            "p": self.device_id,
            "a": self.steam_id,
            "k": conf_key,
            "t": ts,
            "m": "android",
            "tag": tag,
        }

    async def _update_confirmation(self: "SteamClient", conf: Confirmation):
        # create ident code from info to bind conf to listing without id (newly created)
        params = await self._create_confirmation_params(f"details{conf.id}")
        r = await self.session.get(CONF_URL / f"details/{conf.id}", params=params)
        rj = await r.json()
        if not rj.get("success"):
            raise ApiError(f"Failed to fetch confirmation [{conf.id}] details.", rj)
        data: dict[str, ...] = loads(ITEM_INFO_RE.search(rj["html"])["item_info"])
        conf.asset_ident_code = create_ident_code(data["id"], data["appid"], data["contextid"])
