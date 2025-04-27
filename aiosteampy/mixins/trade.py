from typing import overload, Literal, TypeAlias, Sequence, AsyncIterator
from datetime import datetime
from json import dumps as jdumps

from yarl import URL

from ..typed import TradeOffersSummary
from ..constants import STEAM_URL, CORO, T_HEADERS, T_PARAMS, T_PAYLOAD, AppContext, App
from ..exceptions import EResultError, SteamError
from ..models import (
    TradeOffer,
    TradeOfferItem,
    TradeOfferStatus,
    HistoryTradeOffer,
    HistoryTradeOfferItem,
    EconItem,
)
from ..utils import create_ident_code, to_int_boolean, steam_id_to_account_id, account_id_to_steam_id
from .public import SteamCommunityPublicMixin, T_SHARED_DESCRIPTIONS
from .web_api import SteamWebApiMixin

T_TRADE_OFFERS_DATA: TypeAlias = tuple[list[TradeOffer], list[TradeOffer], int]


class TradeMixin(SteamWebApiMixin, SteamCommunityPublicMixin):
    """
    Mixin with trade offers related methods.
    Depends on `ConfirmationMixin`, `SteamCommunityPublicMixin`.
    """

    __slots__ = ()

    async def get_trade_offer(
        self,
        offer_id: int,
        *,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
    ) -> TradeOffer:
        """
        Fetch trade offer from Steam.

        :param offer_id:
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :raises EResultError: for ordinary reasons
        """

        params = {
            "tradeofferid": offer_id,
            "language": self.language,
            "get_descriptions": 1,
            **params,
        }

        try:
            rj = await self.call_web_api(STEAM_URL.API.IEconService.GetTradeOffer, params=params, headers=headers)
        except EResultError as e:
            raise EResultError("Failed to fetch trade offer", e.result, e.data) from e

        data: dict[str, dict | list[dict]] = rj["response"]

        if _item_descriptions_map is None:
            _item_descriptions_map = {}

        if "descriptions" in data:
            self._update_item_descrs_map_from_trades(data["descriptions"], _item_descriptions_map)

        return self._create_trade_offer(data["offer"], _item_descriptions_map)

    @classmethod
    def _update_item_descrs_map_from_trades(cls, descrs: list[dict], item_descrs_map: T_SHARED_DESCRIPTIONS):
        for d_data in descrs:
            key = create_ident_code(d_data["instanceid"], d_data["classid"], d_data["appid"])
            if key not in item_descrs_map:
                item_descrs_map[key] = cls._create_item_descr(d_data)

    def _create_trade_offer(self, data: dict, item_descrs_map: T_SHARED_DESCRIPTIONS) -> TradeOffer:
        return TradeOffer(
            id=int(data["tradeofferid"]),
            owner_id=self.steam_id,
            partner_id=data["accountid_other"],
            is_our_offer=data["is_our_offer"],
            expiration_time=datetime.fromtimestamp(data["expiration_time"]),
            time_created=datetime.fromtimestamp(data["time_created"]),
            time_updated=datetime.fromtimestamp(data["time_updated"]),
            items_to_give=self._parse_items_for_trade(data.get("items_to_give", ()), item_descrs_map),
            items_to_receive=self._parse_items_for_trade(data.get("items_to_receive", ()), item_descrs_map),
            message=data["message"],
            status=TradeOfferStatus(data["trade_offer_state"]),
        )

    @classmethod
    def _parse_items_for_trade(cls, items: list[dict], item_descrs_map: T_SHARED_DESCRIPTIONS) -> list[TradeOfferItem]:
        return [
            TradeOfferItem(
                asset_id=int(a_data["assetid"]),
                amount=int(a_data["amount"]),
                missing=a_data["missing"],
                est_usd=int(a_data.get("est_usd", 0)),
                app_context=AppContext((App(int(a_data["appid"])), int(a_data["contextid"]))),
                description=item_descrs_map.get(
                    create_ident_code(
                        a_data["instanceid"],
                        a_data["classid"],
                        a_data["appid"],
                    )
                ),
            )
            for a_data in items
        ]

    @overload
    async def get_trade_offers(
        self,
        *,
        time_historical_cutoff: int | datetime = ...,
        sent: bool = ...,
        received: bool = ...,
        cursor: int = ...,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> T_TRADE_OFFERS_DATA:
        ...

    @overload
    async def get_trade_offers(
        self,
        *,
        historical_only: Literal[True] = ...,
        sent: bool = ...,
        received: bool = ...,
        cursor: int = ...,
        params: T_PARAMS = ...,
        headers: T_HEADERS = ...,
    ) -> T_TRADE_OFFERS_DATA:
        ...

    async def get_trade_offers(
        self,
        *,
        active_only=True,
        time_historical_cutoff: int | datetime = None,
        historical_only=False,
        sent=True,
        received=True,
        cursor=0,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
    ) -> T_TRADE_OFFERS_DATA:
        """
        Fetch trade offers from `Steam Web Api`.

        .. note:: You can paginate by yourself passing `cursor` arg.
            Returned cursor with 0 value means that there is no more pages

        .. seealso:: https://steamapi.xpaw.me/#IEconService/GetTradeOffers

        :param active_only: fetch active, changed since `time_historical_cutoff` tradeoffs only or not
        :param time_historical_cutoff: timestamp for `active_only`
        :param historical_only: opposite for `active_only`
        :param sent: include sent offers or not
        :param received: include received offers or not
        :param cursor: cursor integer, need to paginate over
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: sent trades, received trades lists, next cursor
        :raises EResultError: for ordinary reasons
        :raises TypeError:
        """

        if historical_only:
            if time_historical_cutoff is not None:
                raise TypeError("Argument `time_historical_cutoff` must be used only with `active_only`")

            active_only = False

        params = {
            "active_only": to_int_boolean(active_only),
            "get_sent_offers": to_int_boolean(sent),
            "get_received_offers": to_int_boolean(received),
            "historical_only": to_int_boolean(historical_only),
            "get_descriptions": 1,
            "cursor": cursor,
            "language": self.language,
            **params,
        }
        if active_only and time_historical_cutoff is not None:
            if isinstance(time_historical_cutoff, datetime):
                params["time_historical_cutoff"] = int(time_historical_cutoff.timestamp())  # trunc ms
            else:  # int ts
                params["time_historical_cutoff"] = time_historical_cutoff

        if _item_descriptions_map is None:
            _item_descriptions_map = {}

        try:
            rj = await self.call_web_api(STEAM_URL.API.IEconService.GetTradeOffers, params=params, headers=headers)
        except EResultError as e:
            raise EResultError("Failed to fetch trade offers", e.result, e.data) from e

        data: dict[str, dict | list[dict]] = rj["response"]
        next_cursor = data.get("next_cursor", 0)

        if "descriptions" in data:
            self._update_item_descrs_map_from_trades(data["descriptions"], _item_descriptions_map)

        return (
            [self._create_trade_offer(d, _item_descriptions_map) for d in data.get("trade_offers_sent", ())],
            [self._create_trade_offer(d, _item_descriptions_map) for d in data.get("trade_offers_received", ())],
            next_cursor,
        )

    # PyCharm doesn't like overloads and AsyncIterators being combined, well so
    # @overload
    # async def trade_offers(
    #     self,
    #     *,
    #     time_historical_cutoff: int | datetime = ...,
    #     sent: bool = ...,
    #     received: bool = ...,
    #     cursor: int = ...,
    #     params: T_PARAMS = ...,
    #     headers: T_HEADERS = ...,
    # ) -> AsyncIterator[T_TRADE_OFFERS_DATA]:
    #     ...
    #
    # @overload
    # async def trade_offers(
    #     self,
    #     *,
    #     historical_only: Literal[True] = ...,
    #     sent: bool = ...,
    #     received: bool = ...,
    #     cursor: int = ...,
    #     params: T_PARAMS = ...,
    #     headers: T_HEADERS = ...,
    # ) -> AsyncIterator[T_TRADE_OFFERS_DATA]:
    #     ...

    async def trade_offers(
        self,
        *,
        active_only=True,
        time_historical_cutoff: int | datetime = None,
        historical_only=False,
        sent=True,
        received=True,
        cursor=0,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
    ) -> AsyncIterator[T_TRADE_OFFERS_DATA]:
        """
        Fetch trade offers from `Steam Web Api`. Return async iterator to paginate over offers pages.

        .. note:: Method requires API key

        :param active_only: fetch active, changed since `time_historical_cutoff` tradeoffs only or not
        :param time_historical_cutoff: timestamp for `active_only`
        :param historical_only: opposite for `active_only`
        :param sent: include sent offers or not
        :param received: include received offers or not
        :param cursor: cursor integer, need to paginate over offer pages
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: `AsyncIterator` that yields sent trades, received trades lists, next cursor
        :raises EResultError: for ordinary reasons
        :raises TypeError:
        """

        if _item_descriptions_map is None:
            _item_descriptions_map = {}

        more_offers = True
        while more_offers:
            # avoid excess destructuring
            offers_data = await self.get_trade_offers(
                active_only=active_only,
                time_historical_cutoff=time_historical_cutoff,
                historical_only=historical_only,
                sent=sent,
                received=received,
                cursor=cursor,
                params=params,
                headers=headers,
                _item_descriptions_map=_item_descriptions_map,
            )
            cursor = offers_data[2]
            more_offers = bool(cursor)

            yield offers_data

    # TODO async iterators over specific type of offers, like `sent_trade_offers`, `received_trade_offers`

    async def get_trade_offers_summary(self, *, params: T_PARAMS = {}, headers: T_HEADERS = {}) -> TradeOffersSummary:
        """
        Get trade offers summary from Steam Web Api.

        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: trade offers summary
        :raises EResultError:
        """

        try:
            rj: dict[str, TradeOffersSummary] = await self.call_web_api(
                STEAM_URL.API.IEconService.GetTradeOffersSummary,
                params=params,
                headers=headers,
            )
        except EResultError as e:
            raise EResultError("Failed to fetch trade offers summary", e.result, e.data) from e

        return rj["response"]

    async def get_trade_receipt(
        self,
        offer_id: int,
        *,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
    ) -> HistoryTradeOffer:
        """
        Fetch single trade offer from history.

        :param offer_id:
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: `HistoryTradeOffer`
        :raises EResultError: for ordinary reasons
        """

        params = {
            "tradeid": offer_id,
            "get_descriptions": 1,
            "language": self.language,
            **params,
        }
        try:
            rj = await self.call_web_api(STEAM_URL.API.IEconService.GetTradeStatus, params=params, headers=headers)
        except EResultError as e:
            raise EResultError("Failed to fetch trade receipt", e.result, e.data) from e

        if _item_descriptions_map is None:
            _item_descriptions_map = {}

        data: dict[str, int | bool | dict | list[dict]] = rj["response"]
        self._update_item_descrs_map_from_trades(data["descriptions"], _item_descriptions_map)

        return self._create_history_trade_offer(data["trades"][0], _item_descriptions_map)

    async def get_trade_history(
        self,
        *,
        max_trades=100,
        start_after_time=0,
        start_after_trade_id=0,
        navigating_back=False,
        include_failed=True,
        params: T_PARAMS = {},
        headers: T_HEADERS = {},
        _item_descriptions_map: T_SHARED_DESCRIPTIONS = None,
    ) -> tuple[list[HistoryTradeOffer], int]:
        """
        Fetch history trades with changed assets data.
        You can paginate by yourself with this method.

        .. note:: Method requires API key

        :param max_trades: page size
        :param start_after_time: timestamp
        :param start_after_trade_id:
        :param navigating_back:
        :param include_failed:
        :param params: extra params to pass to url
        :param headers: extra headers to send with request
        :return: list of `HistoryTradeOffer`, total trades count
        :raises EResultError: for ordinary reasons
        """

        params = {
            "max_trades": max_trades,
            "get_descriptions": 1,
            "include_total": 1,
            "include_failed": to_int_boolean(include_failed),
            "navigating_back": to_int_boolean(navigating_back),
            "start_after_time": start_after_time,
            "start_after_tradeid": start_after_trade_id,
            "language": self.language,
            **params,
        }
        try:
            rj = await self.call_web_api(STEAM_URL.API.IEconService.GetTradeHistory, params=params, headers=headers)
        except EResultError as e:
            raise EResultError("Failed to fetch trades history", e.result, e.data) from e

        if _item_descriptions_map is None:
            _item_descriptions_map = {}

        data: dict[str, int | bool | dict | list[dict]] = rj["response"]
        self._update_item_descrs_map_from_trades(data["descriptions"], _item_descriptions_map)

        return (
            [self._create_history_trade_offer(d, _item_descriptions_map) for d in data["trades"]],
            data["total_trades"],
        )

    def _create_history_trade_offer(self, data: dict, item_descrs_map: T_SHARED_DESCRIPTIONS) -> HistoryTradeOffer:
        return HistoryTradeOffer(
            id=int(data["tradeid"]),
            owner_id=self.steam_id,
            partner_id=steam_id_to_account_id(int(data["steamid_other"])),
            time_init=datetime.fromtimestamp(data["time_init"]),
            status=TradeOfferStatus(data["status"]),
            assets_given=self._parse_items_for_history_trades(data.get("assets_given", ()), item_descrs_map),
            assets_received=self._parse_items_for_history_trades(data.get("assets_received", ()), item_descrs_map),
        )

    @classmethod
    def _parse_items_for_history_trades(
        cls,
        items: list[dict],
        item_descrs_map: T_SHARED_DESCRIPTIONS,
    ) -> list[HistoryTradeOfferItem]:
        return [
            HistoryTradeOfferItem(
                asset_id=int(a_data["assetid"]),
                amount=int(a_data["amount"]),
                new_asset_id=int(a_data["new_assetid"]),
                new_context_id=int(a_data["new_contextid"]),
                app_context=AppContext((App(int(a_data["appid"])), int(a_data["contextid"]))),
                description=item_descrs_map.get(
                    create_ident_code(
                        a_data["instanceid"],
                        a_data["classid"],
                        a_data["appid"],
                    )
                ),
            )
            for a_data in items
        ]

    async def perform_action_with_offer(
        self,
        offer_id: int,
        action: Literal["cancel", "decline"],
        payload: T_PAYLOAD,
        headers: T_HEADERS,
    ) -> dict[str, str]:
        """Cancel or decline trade offer"""

        r = await self.session.post(
            STEAM_URL.TRADE / f"{offer_id}/{action}",
            data={"sessionid": self.session_id, **payload},
            headers=headers,
        )
        # TODO TypedDict
        return await r.json()

    async def cancel_trade_offer(self, obj: int | TradeOffer, *, payload: T_PAYLOAD = {}, headers: T_HEADERS = {}):
        """
        Cancel outgoing trade offer.

        :param obj:
        :param payload: extra payload data
        :param headers: extra headers to send with request
        :raises TypeError:
        :raises EResultError:
        """

        if isinstance(obj, TradeOffer):
            if not obj.is_our_offer:
                raise TypeError("You can't cancel not your offer! Are you trying to decline incoming offer?")
            offer_id = obj.id
        else:
            offer_id = obj
        offer_data = await self.perform_action_with_offer(offer_id, "cancel", payload, headers)
        resp_offer_id = int(offer_data.get("tradeofferid", 0))
        if not resp_offer_id or resp_offer_id != offer_id:
            raise SteamError(f"Failed to cancel trade offer", offer_data)

    async def decline_trade_offer(self, obj: int | TradeOffer, *, payload: T_PAYLOAD = {}, headers: T_HEADERS = {}):
        """
        Decline incoming trade offer.

        :param obj:
        :param payload: extra payload data
        :param headers: extra headers to send with request
        :raises TypeError:
        :raises EResultError:
        """

        if isinstance(obj, TradeOffer):
            if obj.is_our_offer:
                raise TypeError("You can't decline your offer! Are you trying to cancel outgoing offer?")
            offer_id = obj.id
        else:
            offer_id = obj
        offer_data = await self.perform_action_with_offer(offer_id, "decline", payload, headers)
        resp_offer_id = int(offer_data.get("tradeofferid", 0))
        if not resp_offer_id or resp_offer_id != offer_id:
            raise SteamError(f"Failed to decline trade offer", offer_data)

    @overload
    async def accept_trade_offer(
        self,
        obj: TradeOffer,
        *,
        confirm: bool = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ):
        ...

    @overload
    async def accept_trade_offer(
        self,
        obj: int,
        partner: int = ...,
        *,
        confirm: bool = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ):
        ...

    async def accept_trade_offer(
        self,
        obj: int | TradeOffer,
        partner: int = None,
        *,
        confirm=True,
        payload: T_PAYLOAD = {},
        headers: T_HEADERS = {},
    ):
        """
        Accept trade offer, yes.

        .. note::
            Auto confirm accepting if needed.

            If you not pass `partner` but pass `trade offer id` -
            fetches :class:`aiosteampy.models.TradeOffer` from `Steam`.

        :param obj: `TradeOffer` or trade offer id
        :param partner: partner account id (id32) or steam id (id64)
        :param confirm: auto-confirm offer
        :param payload: extra payload data
        :param headers: extra headers to send with request
        :raises EResultError: if there is error when trying to fetch `TradeOffer`
        :raises TypeError:
        """

        if isinstance(obj, TradeOffer):
            if obj.is_our_offer:
                raise TypeError("You can't accept your offer! Are you trying to cancel outgoing offer?")
            offer_id = obj.id
            partner = obj.partner_id64
        else:  # int
            if not partner:
                fetched = await self.get_trade_offer(obj)
                return await self.accept_trade_offer(fetched)

            offer_id = obj
            partner = account_id_to_steam_id(partner) if partner < 4294967296 else partner  # 2**32

        data = {
            "sessionid": self.session_id,
            "tradeofferid": offer_id,
            "serverid": 1,
            "partner": partner,
            "captcha": "",
            **payload,
        }
        url_base = STEAM_URL.TRADE / str(offer_id)
        r = await self.session.post(url_base / "accept", data=data, headers={"Referer": str(url_base), **headers})
        rj: dict = await r.json()
        if rj.get("needs_mobile_confirmation") and confirm:
            await self.confirm_trade_offer(offer_id)

    @overload
    async def make_trade_offer(
        self,
        obj: int,
        to_give: Sequence[EconItem] = ...,
        to_receive: Sequence[EconItem] = ...,
        message: str = ...,
        *,
        token: str = ...,
        confirm: bool = ...,
        countered_id: int = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> int:
        ...

    @overload
    async def make_trade_offer(
        self,
        obj: str,
        to_give: Sequence[EconItem] = ...,
        to_receive: Sequence[EconItem] = ...,
        message: str = ...,
        *,
        confirm: bool = ...,
        countered_id: int = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> int:
        ...

    @overload
    async def make_trade_offer(
        self,
        obj: int,
        to_give: Sequence[EconItem] = ...,
        to_receive: Sequence[EconItem] = ...,
        message: str = ...,
        *,
        token: str = ...,
        fetch: Literal[True] = ...,
        confirm: bool = ...,
        countered_id: int = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> TradeOffer:
        ...

    @overload
    async def make_trade_offer(
        self,
        obj: str,
        to_give: Sequence[EconItem] = ...,
        to_receive: Sequence[EconItem] = ...,
        message: str = ...,
        *,
        fetch: Literal[True] = ...,
        confirm: bool = ...,
        countered_id: int = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> TradeOffer:
        ...

    async def make_trade_offer(
        self,
        obj: int | str,
        to_give: Sequence[EconItem] = (),
        to_receive: Sequence[EconItem] = (),
        message="",
        *,
        token: str = None,
        fetch=False,
        confirm=True,
        countered_id: int = None,
        payload: T_PAYLOAD = {},
        headers: T_HEADERS = {},
    ) -> int | TradeOffer:
        """
        Make (send) steam trade offer to partner.

        .. note:: Make sure that partner is in friends list if you not pass trade url or trade token.

        :param obj: partner trade url, partner id(id32 or id64)
        :param token: trade token (mandatory if `obj` is partner id)
        :param fetch: make a request, fetch and return trade offer
        :param to_give: sequence of items that you want to give
        :param to_receive: sequence of items that you want to receive
        :param message: message to the partner
        :param confirm: auto-confirm offer
        :param countered_id: id of offer that you want to counter. Use `counter_trade_offer` method for this
        :param payload: extra payload data
        :param headers: extra headers to send with request
        :return: trade offer id
        :raises ValueError: trade is empty
        """

        if not to_give and not to_receive:
            raise ValueError("You can't make empty trade offer!")

        trade_url, partner_id32, partner_id64, token = self._parse_make_offer_args(obj, token)
        base_url = STEAM_URL.TRADE / "new/"
        referer = trade_url or base_url % {"partner": partner_id32}
        offer_params = {}
        if token:
            referer %= {"token": token}
            offer_params["trade_offer_access_token"] = token
        data = {
            "sessionid": self.session_id,
            "serverid": 1,
            "partner": partner_id64,
            "tradeoffermessage": message,
            "json_tradeoffer": jdumps(
                {
                    "newversion": True,
                    "version": len(to_give) + len(to_receive) + 1,
                    "me": {"assets": [self._to_asset_dict(i) for i in to_give], "currency": [], "ready": False},
                    "them": {"assets": [self._to_asset_dict(i) for i in to_receive], "currency": [], "ready": False},
                }
            ),
            "captcha": "",
            "trade_offer_create_params": jdumps(offer_params),
            **payload,
        }
        if countered_id:
            data["tradeofferid_countered"] = countered_id

        r = await self.session.post(base_url / "send", data=data, headers={"Referer": str(referer), **headers})
        rj = await r.json()
        offer_id = int(rj["tradeofferid"])
        if confirm and rj.get("needs_mobile_confirmation"):
            conf = await self.confirm_trade_offer(offer_id)
            offer_id = conf.creator_id

        return await self.get_trade_offer(offer_id, headers=headers) if fetch else offer_id

    @staticmethod
    def _to_asset_dict(i: EconItem) -> dict[str, int | str]:
        return {
            "appid": i.app_context.app.value,
            "contextid": str(i.app_context.context),
            "amount": i.amount,
            "assetid": str(i.asset_id),
        }

    @staticmethod
    def _parse_make_offer_args(obj: str | int, token: str | None) -> tuple[str | None, int, int, str | None]:
        trade_url = None
        if isinstance(obj, str):  # trade url
            trade_url = URL(obj)
            partner_id32 = int(trade_url.query["partner"])
            partner_id64 = account_id_to_steam_id(partner_id32)
            token = trade_url.query["token"]
            trade_url = str(trade_url)
        else:
            partner_id = obj
            if partner_id < 4294967296:  # 32
                partner_id32 = partner_id
                partner_id64 = account_id_to_steam_id(partner_id)
            else:  # 64
                partner_id64 = partner_id
                partner_id32 = steam_id_to_account_id(partner_id64)

        return trade_url, partner_id32, partner_id64, token

    @overload
    async def counter_trade_offer(
        self,
        obj: TradeOffer,
        to_give: Sequence[EconItem] = ...,
        to_receive: Sequence[EconItem] = ...,
        message="",
        *,
        confirm: bool = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> int:
        ...

    @overload
    async def counter_trade_offer(
        self,
        obj: int,
        to_give: Sequence[EconItem] = ...,
        to_receive: Sequence[EconItem] = ...,
        message="",
        *,
        partner_id: int,
        confirm: bool = ...,
        payload: T_PAYLOAD = ...,
        headers: T_HEADERS = ...,
    ) -> int:
        ...

    def counter_trade_offer(
        self,
        obj: TradeOffer | int,
        to_give: Sequence[EconItem] = (),
        to_receive: Sequence[EconItem] = (),
        message="",
        *,
        partner_id: int = None,
        confirm=True,
        payload: T_PAYLOAD = {},
        headers: T_HEADERS = {},
    ) -> CORO[int]:
        """
        Counter trade offer with another.

        :param obj: `TradeOffer` or trade offer id of which you want to counter
        :param to_give: sequence of items that you want to give
        :param to_receive: sequence of items that you want to receive
        :param message: message to the partner
        :param partner_id:
        :param confirm: auto-confirm offer
        :param payload: extra payload data
        :param headers: extra headers to send with request
        :return: trade offer id
        :raises TypeError:
        """

        if isinstance(obj, TradeOffer):
            offer_id = obj.id
            to_give_updated = [*obj.items_to_give, *to_give]
            to_receive_updated = [*obj.items_to_receive, *to_receive]
            if obj.is_our_offer:
                raise TypeError("You can't counter your offer!")
        else:  # trade id
            offer_id = obj
            to_give_updated = to_give
            to_receive_updated = to_receive

        return self.make_trade_offer(
            partner_id,
            to_give_updated,
            to_receive_updated,
            message,
            confirm=confirm,
            countered_id=offer_id,
            payload=payload,
            headers=headers,
        )
