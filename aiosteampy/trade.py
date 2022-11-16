from typing import TYPE_CHECKING, overload, Literal, Type, TypeAlias
from datetime import datetime

from .exceptions import ApiError
from .constants import STEAM_URL
from .models import TradeOffer, TradeOfferItem, TradeOfferStatus, ItemClass, HistoryTradeOffer, HistoryTradeOfferItem
from .utils import create_ident_code, to_int_boolean, steam_id_to_account_id, account_id_to_steam_id
from .typed import TradeOffersSummary

if TYPE_CHECKING:
    from .client import SteamClient

__all__ = ("TradeMixin",)

TRADE_OFFERS: TypeAlias = tuple[tuple[TradeOffer, ...], tuple[TradeOffer, ...]]
ERROR_MSG = "You can't accept your offer! Are you trying to cancel outgoing offer?"


class TradeMixin:
    """
    Mixin with trade offers related methods.
    """

    __slots__ = ()

    _trades_storage: dict[int, TradeOffer]

    def __init__(self, *args, **kwargs):
        self._trades_storage = {}

        super().__init__(*args, **kwargs)

    async def get_trade_offer(self: "SteamClient", offer_id: int) -> TradeOffer:
        """Get specific trade."""

        params = {
            "key": self._api_key,
            "tradeofferid": offer_id,
            "language": self.language,
            "get_descriptions": 1,
        }
        r = await self.session.get(STEAM_URL.API.IEconService.GetTradeOffer, params=params)
        rj: dict[str, ...] = await r.json()
        if not rj.get("response"):
            raise ApiError(f"Can't fetch trade offer [{offer_id}].", rj)

        data: dict[str, dict[str, ...] | list[dict[str, ...]]] = rj["response"]
        classes_map = {}
        self._update_classes_map_for_trades(data["descriptions"], classes_map)

        return self._create_trade_offer_from_data(data["offer"], classes_map)

    @classmethod
    def _update_classes_map_for_trades(cls: Type["SteamClient"], data: list[dict], classes_map: dict):
        for desc in data:
            key = create_ident_code(desc["classid"], desc["appid"])
            if key not in classes_map:
                classes_map[key] = cls._create_item_class_from_data(desc, (desc,))

    def _create_trade_offer_from_data(
        self: "SteamClient", data: dict[str, ...], classes_map: dict[str, ItemClass]
    ) -> TradeOffer:
        return TradeOffer(
            id=int(data["tradeofferid"]),
            owner=self.steam_id,
            partner_id=data["accountid_other"],
            is_our_offer=data["is_our_offer"],
            expiration_time=datetime.fromtimestamp(data["expiration_time"]),
            time_created=datetime.fromtimestamp(data["time_created"]),
            time_updated=datetime.fromtimestamp(data["time_updated"]),
            items_to_give=self._parse_assets_for_trade(data.get("items_to_give", ()), classes_map),
            items_to_receive=self._parse_assets_for_trade(data.get("items_to_receive", ()), classes_map),
            message=data["message"] or None,
            status=TradeOfferStatus(data["trade_offer_state"]),
        )

    @classmethod
    def _parse_assets_for_trade(
        cls: Type["SteamClient"],
        items: list[dict[str, ...]],
        classes_map: dict[str, ItemClass],
    ) -> tuple[TradeOfferItem, ...]:
        return tuple(
            TradeOfferItem(
                id=a_data["assetid"],
                class_id=int(a_data["classid"]),
                game=cls._find_game_for_asset(a_data, (a_data,)),
                amount=int(a_data["amount"]),
                class_=classes_map.get(create_ident_code(a_data["classid"], a_data["appid"])),
                missing=a_data["missing"],
                est_usd=int(a_data["est_usd"]),
            )
            for a_data in items
        )

    @overload
    async def get_trade_offers(
        self,
        *,
        time_historical_cutoff: int = ...,
        sent: bool = ...,
        received: bool = ...,
    ) -> TRADE_OFFERS:
        ...

    @overload
    async def get_trade_offers(
        self,
        *,
        active_only: Literal[False],
        historical_only: Literal[True],
        sent: bool = ...,
        received: bool = ...,
    ) -> TRADE_OFFERS:
        ...

    async def get_trade_offers(
        self: "SteamClient",
        *,
        active_only=True,
        time_historical_cutoff: int = None,
        historical_only=False,
        sent=True,
        received=True,
        **kwargs,
    ) -> TRADE_OFFERS:
        """

        :param active_only:
        :param time_historical_cutoff:
        :param historical_only:
        :param sent:
        :param received:
        :return:
        """

        params = {
            "key": self._api_key,
            "active_only": to_int_boolean(active_only),
            "get_sent_offers": to_int_boolean(sent),
            "get_received_offers": to_int_boolean(received),
            "historical_only": to_int_boolean(historical_only),
            "get_descriptions": 1,
            "cursor": 0,
            "language": self.language,
            **kwargs,
        }
        if active_only and time_historical_cutoff is not None:
            params["time_historical_cutoff"] = time_historical_cutoff

        classes_map: dict[str, ItemClass] = {}
        offers_sent = []
        offers_received = []

        while True:
            r = await self.session.get(STEAM_URL.API.IEconService.GetTradeOffers, params=params)
            rj = await r.json()
            if not rj.get("response"):
                raise ApiError(f"Can't fetch trade offers.", rj)

            data: dict[str, dict[str, ...] | list[dict[str, ...]]] = rj["response"]
            offers_sent.extend(data.get("trade_offers_sent", ()))
            offers_received.extend(data.get("trade_offers_received", ()))
            self._update_classes_map_for_trades(data["descriptions"], classes_map)

            params["cursor"] = data.get("next_cursor", 0)
            if not params["cursor"]:
                break

        return tuple(self._create_trade_offer_from_data(d, classes_map) for d in offers_sent), tuple(
            self._create_trade_offer_from_data(d, classes_map) for d in offers_received
        )

    async def get_trade_offers_summary(self: "SteamClient") -> TradeOffersSummary:
        r = await self.session.get(STEAM_URL.API.IEconService.GetTradeOffersSummary, params={"key": self._api_key})
        rj: dict[str, TradeOffersSummary] = await r.json()
        if not rj.get("response"):
            raise ApiError(f"Can't fetch trade offers summary.", rj)

        return rj["response"]

    async def get_trade_receipt(self: "SteamClient", offer_id: int) -> HistoryTradeOffer:
        """
        Fetch single trade offer from history.

        :param offer_id:
        :return:
        """

        params = {
            "key": self._api_key,
            "tradeid": offer_id,
            "get_descriptions": 1,
            "language": self.language,
        }
        r = await self.session.get(STEAM_URL.API.IEconService.GetTradeStatus, params=params)
        rj = await r.json()
        if not rj.get("response"):
            raise ApiError(f"Can't fetch trade status.", rj)

        classes_map = {}
        self._update_classes_map_for_trades(rj["response"]["descriptions"], classes_map)

        return self._create_history_trade_offer_from_data(rj["response"]["trades"][0], classes_map)

    async def get_trade_history(
        self: "SteamClient",
        max_trades=100,
        *,
        start_after_time=0,
        start_after_trade_id=0,
        navigating_back=False,
        include_failed=True,
        **kwargs: dict[str, str | int | float],
    ) -> tuple[tuple[HistoryTradeOffer, ...], int, bool]:
        """

        :param max_trades:
        :param start_after_time:
        :param start_after_trade_id:
        :param navigating_back:
        :param include_failed:
        :return:
        """

        params = {
            "key": self._api_key,
            "max_trades": max_trades,
            "get_descriptions": 1,
            "include_total": 1,
            "include_failed": to_int_boolean(include_failed),
            "navigating_back": to_int_boolean(navigating_back),
            "start_after_time": start_after_time,
            "start_after_tradeid": start_after_trade_id,
            "language": self.language,
            **kwargs,
        }
        r = await self.session.get(STEAM_URL.API.IEconService.GetTradeHistory, params=params)
        rj = await r.json()
        if not rj.get("response"):
            raise ApiError(f"Can't fetch trades history.", rj)

        classes_map = {}
        data: dict[str, int | bool | dict[str, ...] | list[dict[str, ...]]] = rj["response"]
        self._update_classes_map_for_trades(data["descriptions"], classes_map)

        return (
            tuple(self._create_history_trade_offer_from_data(d, classes_map) for d in data["trades"]),
            data["total_trades"],
            data["more"],
        )

    def _create_history_trade_offer_from_data(
        self: "SteamClient",
        data: dict,
        classes_map: dict[str, ItemClass],
    ) -> HistoryTradeOffer:
        return HistoryTradeOffer(
            id=int(data["tradeid"]),
            owner=self.steam_id,
            partner_id=steam_id_to_account_id(int(data["steamid_other"])),
            time_init=datetime.fromtimestamp(data["time_init"]),
            status=TradeOfferStatus(data["status"]),
            assets_given=self._parse_assets_for_history_trades(data.get("assets_given", ()), classes_map),
            assets_received=self._parse_assets_for_history_trades(data.get("assets_received", ()), classes_map),
        )

    @classmethod
    def _parse_assets_for_history_trades(
        cls: Type["SteamClient"],
        items: list[dict[str, ...]],
        classes_map: dict[str, ItemClass],
    ) -> tuple[HistoryTradeOfferItem, ...]:
        return tuple(
            HistoryTradeOfferItem(
                id=int(a_data["assetid"]),
                class_id=int(a_data["classid"]),
                game=cls._find_game_for_asset(a_data, (a_data,)),
                amount=int(a_data["amount"]),
                class_=classes_map.get(create_ident_code(a_data["classid"], a_data["appid"])),
                new_asset_id=int(a_data["new_assetid"]),
                new_context_id=int(a_data["new_contextid"]),
            )
            for a_data in items
        )

    async def _do_action_with_offer(self: "SteamClient", offer_id: int, action: Literal["cancel", "decline"]) -> int:
        r = await self.session.post(STEAM_URL.TRADES / f"{offer_id}/{action}", data={"sessionid": self.session_id})
        rj: dict[str, str] = await r.json()
        return int(rj.get("tradeofferid", 0))

    async def cancel_trade_offer(self: "SteamClient", offer: int | TradeOffer):
        if isinstance(offer, TradeOffer):
            if not offer.is_our_offer:
                raise ValueError("You can't cancel not your offer! Are you trying to decline incoming offer?")
            offer_id = offer.id
        else:
            offer_id = offer
        resp_offer_id = await self._do_action_with_offer(offer_id, "cancel")
        if not resp_offer_id or resp_offer_id != offer_id:
            raise ApiError(f"Error while try to cancel offer [{offer_id}].")

    async def decline_trade_offer(self: "SteamClient", offer: int | TradeOffer):
        if isinstance(offer, TradeOffer):
            if offer.is_our_offer:
                raise ValueError("You can't decline your offer! Are you trying to cancel outgoing offer?")
            offer_id = offer.id
        else:
            offer_id = offer
        resp_offer_id = await self._do_action_with_offer(offer_id, "decline")
        if not resp_offer_id or resp_offer_id != offer_id:
            raise ApiError(f"Error while try to decline offer [{offer_id}].")

    # TODO storage methods

    @overload
    async def accept_trade_offer(self, offer: TradeOffer):
        ...

    @overload
    async def accept_trade_offer(self, offer: int, partner: int = ...):
        ...

    async def accept_trade_offer(self: "SteamClient", offer: int | TradeOffer, partner: int = None):
        """
        Accept trade offer, yes.

        .. note::
            Fetch :py:class:`aiosteampy.models.TradeOffer` if you not pass ``partner`` arg.
            Auto confirm accepting if needed.

        :param offer:
        :param partner: partner account id (id32) or steam id (id64)
        :raises ConfirmationError:
        """

        if isinstance(offer, TradeOffer):
            if offer.is_our_offer:
                raise ValueError(ERROR_MSG)
            offer_id = offer.id
            partner = offer.partner_id64
        else:
            offer_id = offer
            if partner:
                partner = account_id_to_steam_id(partner) if partner < 4294967296 else partner  # 2**32
            else:
                fetched = await self.get_trade_offer(offer_id)
                if fetched.is_our_offer:
                    raise ValueError(ERROR_MSG)
                partner = fetched.partner_id64

        data = {
            "sessionid": self.session_id,
            "tradeofferid": offer_id,
            "serverid": 1,
            "partner": partner,
            "captcha": "",
        }
        url_base = STEAM_URL.TRADES / str(offer_id)
        r = await self.session.post(url_base / "accept", data=data, headers={"Referer": str(url_base)})
        rj: dict[str, ...] = await r.json()
        if rj.get("needs_mobile_confirmation"):
            await self.confirm_trade_offer(offer_id)
