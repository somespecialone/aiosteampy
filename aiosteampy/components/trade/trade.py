import json
import random
from collections.abc import AsyncGenerator, Awaitable, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, overload
from urllib.parse import quote

from yarl import URL

from ...app import App
from ...constants import STEAM_URL, EResult
from ...exceptions import EmailConfirmationRequired, EResultError, MobileConfirmationRequired, SteamError
from ...id import SteamID
from ...models import EconItem
from ...session import SteamSession
from ...transport import TransportResponse
from ...utils import create_ident_code
from ...webapi.services.econ import HISTORY_LIMIT, EconServiceClient
from .._base import BasePublicComponent, EconMixin, ItemDescriptionsMap
from ..state import SteamState
from .models import (
    HistoryTradeOffer,
    HistoryTradeOfferItem,
    HistoryTradeOffers,
    TradeAssetData,
    TradeOffer,
    TradeOfferItem,
    TradeOffers,
    TradeOffersSummary,
    TradeOfferStatus,
)

if TYPE_CHECKING:  # decouple components from guard
    from ...guard.confirmations import SteamConfirmations


TRADE_URL = STEAM_URL.COMMUNITY / "tradeoffer"
TRADE_NEW_URL = TRADE_URL / "new/"


class TradeComponent(BasePublicComponent, EconMixin):
    """Handle trade-related actions."""

    __slots__ = ("_session", "_state", "_conf", "_service")

    def __init__(
        self,
        session: SteamSession,
        state: SteamState,
        confirmations: "SteamConfirmations | None" = None,
    ):
        super().__init__(session.transport)

        self._session = session
        self._state = state
        self._conf = confirmations

        self._service = EconServiceClient(session.webapi)

    @property
    def confirmations(self) -> "SteamConfirmations | None":
        """`Steam` mobile confirmations manager."""
        return self._conf

    @property
    def service(self) -> EconServiceClient:
        """Economy service client."""
        return self._service

    @property
    def token(self) -> str | None:
        """Trade `token` of current user."""
        return self._state.trade_token

    @property
    def url(self) -> URL | None:
        """Trade `url` of current user."""
        if self._state.trade_token:
            return TRADE_NEW_URL % {"partner": self._session.steam_id.account_id, "token": self._state.trade_token}

    async def generate_new_token(self) -> str:
        """Generates new `trade url` alongside `token`. Will update ``state.trade_token``."""

        r = await self._transport.request(
            "POST",
            self._state.profile_url / "tradeoffers/newtradeurl",
            data={"sessionid": self._session.session_id},
            response_mode="json",
        )

        self._state._trade_token = quote(r.content, safe="~()*!.'")  # https://stackoverflow.com/a/72449666/19419998
        return self._state.trade_token

    def acknowledge_rules(self) -> Awaitable[TransportResponse]:
        """
        Acknowledge *trade protection rules*.
        Required only **once for new account** to access trade offers interactions.
        """

        return self._transport.request(
            "POST",
            TRADE_NEW_URL / "acknowledge",
            data={"sessionid": self._session.session_id, "message": 1},
            headers={"Referer": str(self._state.profile_url / "tradeoffers/"), "Origin": str(STEAM_URL.COMMUNITY)},
            redirects=True,  # handle eligibility check
            response_mode="meta",
        )

    @classmethod
    def _update_item_descrs_map_from_trades(cls, descrs: list[dict], item_descrs_map: ItemDescriptionsMap):
        for d_data in descrs:
            key = create_ident_code(d_data["instanceid"], d_data["classid"], d_data["appid"])
            if key not in item_descrs_map:
                item_descrs_map[key] = cls._create_item_descr(d_data)

    @classmethod
    def _parse_items_for_trade(
        cls,
        items: Sequence[dict],
        item_descrs_map: ItemDescriptionsMap,
    ) -> tuple[TradeOfferItem, ...]:
        return tuple(
            TradeOfferItem(
                asset_id=int(a_data["assetid"]),
                app=App(int(a_data["appid"])),
                amount=int(a_data["amount"]),
                missing=a_data["missing"],
                est_usd=int(a_data.get("est_usd", 0)),
                context_id=int(a_data["contextid"]),
                description=item_descrs_map.get(
                    create_ident_code(
                        a_data["instanceid"],
                        a_data["classid"],
                        a_data["appid"],
                    )
                ),
            )
            for a_data in items
        )

    def _create_trade_offer(self, data: dict, item_descrs_map: ItemDescriptionsMap) -> TradeOffer:
        other = SteamID(data["accountid_other"])
        to_give = self._parse_items_for_trade(data.get("items_to_give", ()), item_descrs_map)
        to_receive = self._parse_items_for_trade(data.get("items_to_receive", ()), item_descrs_map)
        if data["is_our_offer"]:
            creator = self._session.steam_id
            partner = other
            to_partner = to_give
            to_creator = to_receive
        else:
            creator = other
            partner = self._session.steam_id
            to_partner = to_receive
            to_creator = to_give

        return TradeOffer(
            querier=self._session.steam_id,
            trade_offer_id=int(data["tradeofferid"]),
            trade_id=int(data["tradeid"]) if "tradeid" in data else None,
            creator=creator,
            partner=partner,
            expires=datetime.fromtimestamp(data["expiration_time"], UTC),
            created_at=datetime.fromtimestamp(data["time_created"], UTC),
            updated_at=datetime.fromtimestamp(data["time_updated"], UTC),
            to_partner=to_partner,
            to_creator=to_creator,
            message=data["message"] or None,
            status=TradeOfferStatus(data["trade_offer_state"]),
            # useless fields: escrow_end_date, confirmation_method, eresult, from_real_time_trade
            # delay_settlement: bool ?
            # settlement_date: int ?
        )

    async def get(self, trade_offer_id: int) -> TradeOffer | None:
        """
        Get single trade offer. Returns ``None`` if offer is not found.

        .. seealso:: https://steamapi.xpaw.me/#IEconService/GetTradeOffer.

        :param trade_offer_id: `trade offer ID` of the, obviously, trade offer. Do not confuse it with ``trade_id``.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        try:
            r = await self._service.get_trade_offer(trade_offer_id, self._state.language)
        except EResultError as e:
            if e.result is EResult.NO_MATCH:
                return None
            raise

        data: dict[str, dict | list[dict]] = r["response"]

        _item_descriptions_map = {}
        if descrs := data.get("descriptions"):
            self._update_item_descrs_map_from_trades(descrs, _item_descriptions_map)

        return self._create_trade_offer(data["offer"], _item_descriptions_map)

    @overload
    async def get_multiple(
        self,
        *,
        time_historical_cutoff: int | datetime | None = ...,
        sent: bool = ...,
        received: bool = ...,
        cursor: int = ...,
    ) -> TradeOffers: ...

    @overload
    async def get_multiple(
        self,
        *,
        historical_only: Literal[True] = ...,
        sent: bool = ...,
        received: bool = ...,
        cursor: int = ...,
    ) -> TradeOffers: ...

    async def get_multiple(
        self,
        *,
        active_only: bool = True,
        historical_cutoff: int | datetime | None = None,
        historical_only: bool = False,
        sent: bool = True,
        received: bool = True,
        cursor: int = 0,
        _item_descriptions_map: ItemDescriptionsMap | None = None,
    ) -> TradeOffers:
        """
        Get multiple trade offers. History trade offers are not included!

        .. note:: Pagination can be achieved by passing ``cursor`` arg.

        .. seealso:: https://steamapi.xpaw.me/#IEconService/GetTradeOffers.

        :param active_only: query only active.
        :param historical_cutoff: `timestamp` for ``active_only``. Must be used only with ``active_only``.
        :param historical_only: opposite for ``active_only``.
        :param sent: whether to include `sent` offers.
        :param received: whether to include `received` offers.
        :param cursor: `next cursor` to paginate over results.
        :return: sent trades, received trades, next cursor.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        if historical_only:
            if historical_cutoff is not None:
                raise ValueError("Argument `historical_cutoff` must be used only with `active_only`")

            active_only = False

        r = await self._service.get_trade_offers(  # return 0 offers if used with api key
            active_only=active_only,
            time_historical_cutoff=historical_cutoff,
            historical_only=historical_only,
            get_sent_offers=sent,
            get_received_offers=received,
            cursor=cursor,
            language=self._state.language,
        )

        data: dict[str, dict | list[dict]] = r["response"]

        _item_descriptions_map = {} if _item_descriptions_map is None else _item_descriptions_map
        if descrs := data.get("descriptions"):
            self._update_item_descrs_map_from_trades(descrs, _item_descriptions_map)

        return TradeOffers(
            [self._create_trade_offer(d, _item_descriptions_map) for d in data.get("trade_offers_sent", ())],
            [self._create_trade_offer(d, _item_descriptions_map) for d in data.get("trade_offers_received", ())],
            data.get("next_cursor", 0),
        )

    @overload
    async def offers(
        self,
        *,
        time_historical_cutoff: int | datetime | None = ...,
        sent: bool = ...,
        received: bool = ...,
        cursor: int = ...,
    ) -> AsyncGenerator[TradeOffers, None]: ...

    @overload
    async def offers(
        self,
        *,
        historical_only: Literal[True] = ...,
        sent: bool = ...,
        received: bool = ...,
        cursor: int = ...,
    ) -> AsyncGenerator[TradeOffers, None]: ...

    async def offers(
        self,
        *,
        active_only: bool = True,
        time_historical_cutoff: int | datetime | None = None,
        historical_only: bool = False,
        sent: bool = True,
        received: bool = True,
        cursor: int = 0,
    ) -> AsyncGenerator[TradeOffers, None]:
        """
        Get async iterator of trade offers.

        .. seealso:: https://steamapi.xpaw.me/#IEconService/GetTradeOffers.

        :param active_only: query only active.
        :param time_historical_cutoff: `timestamp` for ``active_only``. Must be used only with ``active_only``.
        :param historical_only: opposite for ``active_only``.
        :param sent: whether to include `sent` offers.
        :param received: whether to include `received` offers.
        :param cursor: `next cursor` to paginate over results.
        :return: sent trades, received trades, next cursor.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        _item_descriptions_map = {}

        more_offers = True
        while more_offers:
            offers = await self.get_multiple(
                active_only=active_only,
                historical_cutoff=time_historical_cutoff,
                historical_only=historical_only,
                sent=sent,
                received=received,
                cursor=cursor,
                _item_descriptions_map=_item_descriptions_map,
            )
            cursor = offers.cursor
            more_offers = bool(cursor)

            yield offers

    async def get_summary(self, last_visit: int | datetime | None = None) -> TradeOffersSummary:
        """Get trade offers summary."""

        r = await self._service.get_trade_offers_summary(last_visit)
        data = r["response"]
        return TradeOffersSummary(
            pending_received=data["pending_received_count"],
            new_received=data["new_received_count"],
            updated_received=data["updated_received_count"],
            historical_received=data["historical_received_count"],
            pending_sent=data["pending_sent_count"],
            newly_accepted_sent=data["newly_accepted_sent_count"],
            updated_sent=data["updated_sent_count"],
            historical_sent=data["historical_sent_count"],
            escrow_received=data["escrow_received_count"],
            escrow_sent=data["escrow_sent_count"],
        )

    @classmethod
    def _parse_items_for_history_trades(
        cls,
        items: Sequence[dict],
        item_descrs_map: ItemDescriptionsMap,
    ) -> tuple[HistoryTradeOfferItem, ...]:
        return tuple(
            HistoryTradeOfferItem(
                asset_id=int(a_data["assetid"]),
                amount=int(a_data["amount"]),
                app=App(int(a_data["appid"])),
                context_id=int(a_data["contextid"]),
                new_asset_id=int(a_data.get("new_assetid", a_data.get("assetid", 0))),
                new_context_id=int(a_data.get("new_contextid", a_data.get("contextid", 0))),
                description=item_descrs_map.get(
                    create_ident_code(
                        a_data["instanceid"],
                        a_data["classid"],
                        a_data["appid"],
                    )
                ),
            )
            for a_data in items
        )

    def _create_history_trade_offer(self, data: dict, item_descrs_map: ItemDescriptionsMap) -> HistoryTradeOffer:
        return HistoryTradeOffer(
            querier=self._session.steam_id,
            trade_id=int(data["tradeid"]),
            partners=(self._session.steam_id, SteamID(data["steamid_other"])),
            init=datetime.fromtimestamp(data["time_init"], UTC),
            status=TradeOfferStatus(data["status"]),
            settlement=datetime.fromtimestamp(data["time_settlement"], UTC) if "time_settlement" in data else None,
            mod=datetime.fromtimestamp(data["time_mod"], UTC) if "time_mod" in data else None,
            to_partner_a=self._parse_items_for_history_trades(data.get("assets_received", ()), item_descrs_map),
            to_partner_b=self._parse_items_for_history_trades(data.get("assets_given", ()), item_descrs_map),
        )

    async def get_receipt(self, trade_id: int) -> HistoryTradeOffer | None:
        """
        Get trade offer `receipt` from history of **accepted** trade offers.
        Returns ``None`` if offer is not found.

        .. seealso:: https://steamapi.xpaw.me/#IEconService/GetTradeStatus.

        :param trade_id: `trade ID` of **accepted trade offer**. Do not confuse it with ``trade_offer_id``.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        try:
            r = await self._service.get_trade_status(trade_id, self._state.language)
        except EResultError as e:
            if e.result is EResult.NO_MATCH:
                return None
            raise

        data: dict[str, int | bool | dict | list[dict]] = r["response"]

        _item_descriptions_map = {}
        if descrs := data.get("descriptions"):
            self._update_item_descrs_map_from_trades(descrs, _item_descriptions_map)

        return self._create_history_trade_offer(data["trades"][0], _item_descriptions_map)

    async def get_history(
        self,
        *,
        max_trades: int = HISTORY_LIMIT,
        start_after_time: int | datetime | None = None,
        start_after_trade_id: int | None = None,
        navigating_back: bool = False,
        # include_failed: bool = True,  # ?
        _item_descriptions_map: ItemDescriptionsMap | None = None,
    ) -> HistoryTradeOffers:
        """
        Get trade history.

        .. note::
            Pagination can be achieved by passing ``start_after_time`` or ``start_after_trade_id`` arg,
            direction depends on ``navigating_back`` arg.
            Limit per page can be effectively increased by using `Steam Web API` key instead of `access token`.

        .. seealso:: https://steamapi.xpaw.me/#IEconService/GetTradeHistory.

        :param max_trades: number of trades to get information for.
        :param start_after_time: `timestamp` to start after for pagination.
        :param start_after_trade_id: `trade ID` to start after for pagination.
        :param navigating_back: whether to navigate backwards.
        :return: list of `history trade offers`, total `trades` count, next `trade ID`,
            next `trade time`, whether there are more `trades`.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        r = await self._service.get_trade_history(
            max_trades=max_trades,
            start_after_time=start_after_time,
            start_after_trade_id=start_after_trade_id,
            navigating_back=navigating_back,
            language=self._state.language,
            # include_failed=include_failed,
        )

        data: dict[str, int | bool | dict | list[dict]] = r["response"]

        _item_descriptions_map = {} if _item_descriptions_map is None else _item_descriptions_map
        if descrs := data.get("descriptions"):
            self._update_item_descrs_map_from_trades(descrs, _item_descriptions_map)

        trades = [self._create_history_trade_offer(d, _item_descriptions_map) for d in data["trades"]]
        if trades:
            trade = trades[0] if navigating_back else trades[-1]
            next_trade_id = trade.trade_id
            next_time = trade.init
        else:
            next_trade_id = None
            next_time = None
        return HistoryTradeOffers(trades, data["total_trades"], next_trade_id, next_time, data["more"])

    async def history(
        self,
        *,
        max_trades: int = HISTORY_LIMIT,
        start_after_time: int | datetime | None = None,
        start_after_trade_id: int | None = None,
        navigating_back: bool = False,
    ) -> AsyncGenerator[list[HistoryTradeOffer], None]:
        """
        Get async iterator of trade history.

        .. seealso:: https://steamapi.xpaw.me/#IEconService/GetTradeHistory.

        :param max_trades: number of trades to get per page.
        :param start_after_time: `timestamp` to start after for pagination.
        :param start_after_trade_id: `trade ID` to start after for pagination.
        :param navigating_back: whether to navigate backwards.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        _item_descriptions_map = {}

        more_history = True
        while more_history:
            history = await self.get_history(
                max_trades=max_trades,
                start_after_time=start_after_time,
                start_after_trade_id=start_after_trade_id,
                navigating_back=navigating_back,
                _item_descriptions_map=_item_descriptions_map,
            )
            if not history.trades:
                more_history = False
            else:
                yield history.trades
                more_history = history.more
                start_after_trade_id = history.next_trade_id
                start_after_time = history.next_time

    async def _perform_offer_action(
        self,
        trade_offer_id: int,
        action: Literal["cancel", "decline", "accept"],
        data: dict | None = None,
    ) -> dict[str, str]:
        url_base = TRADE_URL / str(trade_offer_id)
        r = await self._transport.request(
            "POST",
            url_base / action,
            data={"sessionid": self._session.session_id, **(data or {})},
            headers={"Referer": str(url_base)},
            response_mode="json",
        )
        return r.content

    async def cancel(self, obj: int | TradeOffer):
        """
        Cancel outgoing `trade offer`.

        :param obj: ``TradeOffer`` or `trade offer ID`.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises SteamError: failed to perform action with `trade offer`.
        """

        if isinstance(obj, TradeOffer):
            if obj.creator != self._session.steam_id:
                raise TypeError(
                    f"User({self._session.steam_id}) is not offer({obj.trade_offer_id}) creator({obj.creator}). "
                    "Are you trying to decline incoming offer?"
                )
            offer_id = obj.trade_offer_id
        else:
            offer_id = obj

        offer_data = await self._perform_offer_action(offer_id, "cancel")
        resp_offer_id = int(offer_data.get("tradeofferid", 0))
        if not resp_offer_id or resp_offer_id != offer_id:
            raise SteamError(f"Failed to cancel trade offer", offer_data)

    async def decline(self, obj: int | TradeOffer):
        """
        Decline incoming `trade offer`.

        :param obj: ``TradeOffer`` or `trade offer ID`.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises SteamError: failed to perform action with `trade offer`.
        """

        if isinstance(obj, TradeOffer):
            if obj.partner != self._session.steam_id:
                raise TypeError(
                    f"User({self._session.steam_id}) is not offer({obj.trade_offer_id}) partner({obj.partner}). "
                    "Are you trying to cancel outgoing offer?"
                )
            offer_id = obj.trade_offer_id
        else:
            offer_id = obj

        offer_data = await self._perform_offer_action(offer_id, "decline")
        resp_offer_id = int(offer_data.get("tradeofferid", 0))
        if not resp_offer_id or resp_offer_id != offer_id:
            raise SteamError(f"Failed to decline trade offer", offer_data)

    @overload
    async def accept(self, obj: TradeOffer): ...

    @overload
    async def accept(self, obj: int, partner: SteamID = ...): ...

    async def accept(self, obj: int | TradeOffer, partner: SteamID | None = None):
        """
        Accept incoming `trade offer`.

        .. note::
            Will confirm `trade offer` if ``confirmations`` is present.
            Will query ``TradeOffer`` from `Steam` if `trade offer id` is passed without ``partner``.

        :param obj: ``TradeOffer`` or `trade offer id`.
        :param partner: partner that sent the offer.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises EmailConfirmationRequired: action requires `email` confirmation.
        :raises MobileConfirmationRequired: action requires `mobile` confirmation.
        """

        if isinstance(obj, TradeOffer):
            if obj.partner != self._session.steam_id:
                raise TypeError(
                    f"User({self._session.steam_id}) is not offer({obj.trade_offer_id}) partner({obj.partner})."
                )
            offer_id = obj.trade_offer_id
            partner = obj.partner
        else:  # int
            if partner is None:
                obj = await self.get(obj)
                return await self.accept(obj)

            offer_id = obj

        data = {
            "tradeofferid": offer_id,
            "serverid": 1,
            "partner": partner,
            "captcha": "",
        }
        data = await self._perform_offer_action(offer_id, "accept", data)
        if data.get("needs_email_confirmation"):
            raise EmailConfirmationRequired

        if data.get("needs_mobile_confirmation"):
            if self._conf is None:
                raise MobileConfirmationRequired(offer_id)

            await self._conf.confirm_trade_offer(offer_id)

    @staticmethod
    def _convert_verify_asset(i: EconItem | TradeAssetData, owner: SteamID) -> TradeAssetData:
        """Convert ``EconItem`` to ``TradeAssetData``. Verify that ``owner`` is the owner of the item."""

        if isinstance(i, EconItem):
            if i.owner != owner:
                raise ValueError(f"Item({i.id}) is not owned by user({owner}).")

            return {
                "appid": i.description.app.id,
                "contextid": str(i.context_id),
                "amount": str(i.amount),
                "assetid": str(i.asset_id),
            }

        return i

    @overload
    async def send(
        self,
        obj: str | URL,
        to_partner: Sequence[EconItem | TradeAssetData] = ...,
        from_partner: Sequence[EconItem | TradeAssetData] = ...,
        message: str = ...,
        *,
        countered_id: int = ...,
    ) -> int: ...

    @overload
    async def send(
        self,
        obj: SteamID,
        to_partner: Sequence[EconItem | TradeAssetData] = ...,
        from_partner: Sequence[EconItem | TradeAssetData] = ...,
        message: str = ...,
        *,
        token: str = ...,
        countered_id: int = ...,
    ) -> int: ...

    async def send(
        self,
        obj: SteamID | str | URL,
        to_partner: Sequence[EconItem | TradeAssetData] = (),
        from_partner: Sequence[EconItem | TradeAssetData] = (),
        message: str = "",
        *,
        token: str | None = None,
        countered_id: int | None = None,
    ) -> int:
        """
        Send `trade offer` to `partner`.

        .. note::
            `Partner` must be in friends list of current user
            if `trade url` or ``token`` are not provided.

        :param obj: partner `trade url` or ``SteamID``.
        :param token: `trade token` from `trade url`.
            Need to be provided if ``obj`` is `partner` `steam ID` or
            `partner` is not in friends list of current user.
        :param to_partner: items that will be sent to `partner`.
        :param from_partner: items that will be received from `partner`.
        :param message: message that will attached to the offer.
        :param countered_id: `trade offer ID` of offer that needs to be `countered`.
        :return: `trade offer ID`.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises EmailConfirmationRequired: action requires `email` confirmation.
        :raises MobileConfirmationRequired: action requires `mobile` confirmation.
        """

        if not to_partner and not from_partner:
            raise ValueError("Trade offer must have at least one item to send or receive.")

        # prepare args
        if isinstance(obj, (str, URL)):
            if isinstance(obj, str):  # avoid double conversion
                trade_url = obj
                obj = URL(obj)
            else:
                trade_url = str(obj)

            partner = SteamID(obj.query["partner"])
            token = obj.query["token"]
        else:
            partner = obj
            trade_url = None

        # prepare referer
        if countered_id:
            referer = TRADE_URL / f"{countered_id}/"
        else:
            referer = trade_url or (TRADE_NEW_URL % {"partner": partner.id32})

        offer_params = {}
        if token:
            referer %= {"token": token}
            offer_params["trade_offer_access_token"] = token
        data = {
            "sessionid": self._session.session_id,
            "serverid": 1,
            "partner": partner,
            "tradeoffermessage": message,
            "json_tradeoffer": json.dumps(
                {
                    "newversion": True,
                    # counter of user actions with items in trade offer window, does not matter much
                    "version": len(to_partner) + len(from_partner) + random.choice(range(1, 10)),
                    "me": {
                        "assets": [self._convert_verify_asset(i, self._session.steam_id) for i in to_partner],
                        "currency": [],
                        "ready": False,
                    },
                    "them": {
                        "assets": [self._convert_verify_asset(i, partner) for i in from_partner],
                        "currency": [],
                        "ready": False,
                    },
                }
            ),
            "captcha": "",
            "trade_offer_create_params": json.dumps(offer_params),
        }
        if countered_id:
            data["tradeofferid_countered"] = countered_id

        r = await self._transport.request(
            "POST",
            TRADE_NEW_URL / "send",
            data=data,
            headers={"Referer": str(referer)},
            response_mode="json",
        )
        rj = r.content

        if rj.get("needs_email_confirmation"):
            raise EmailConfirmationRequired

        offer_id = int(rj["tradeofferid"])
        if rj.get("needs_mobile_confirmation"):
            if self._conf is None:
                raise MobileConfirmationRequired(offer_id)

            await self._conf.confirm_trade_offer(offer_id)

        return offer_id

    @overload
    async def counter(
        self,
        obj: TradeOffer,
        to_partner: Sequence[EconItem | TradeAssetData] = ...,
        from_partner: Sequence[EconItem | TradeAssetData] = ...,
        message: str = ...,
    ) -> int: ...

    @overload
    async def counter(
        self,
        obj: int,
        to_partner: Sequence[EconItem | TradeAssetData] = ...,
        from_partner: Sequence[EconItem | TradeAssetData] = ...,
        message: str = ...,
        *,
        partner: SteamID,
    ) -> int: ...

    def counter(
        self,
        obj: TradeOffer | int,
        to_partner: Sequence[EconItem | TradeAssetData] = (),
        from_partner: Sequence[EconItem | TradeAssetData] = (),
        message: str = "",
        *,
        partner: SteamID | None = None,
    ) -> Awaitable[int]:
        """
        Counter `trade offer` with another.

        :param obj: `TradeOffer` or `trade offer ID` of countered offer.
        :param to_partner: items that will be sent to `partner`.
        :param from_partner: items that will be received from `partner`.
        :param message: message that will be attached to the offer.
        :param partner: user from which offer has been sent.
        :return: `trade offer ID`.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises EmailConfirmationRequired: action requires `email` confirmation.
        :raises MobileConfirmationRequired: action requires `mobile` confirmation.
        """

        if isinstance(obj, TradeOffer):
            if obj.partner != self._session.steam_id:
                raise TypeError(
                    f"User({self._session.steam_id}) is not offer({obj.trade_offer_id}) partner({obj.partner})."
                )
            countered_id = obj.trade_offer_id
            partner = obj.creator
        else:  # trade offer id
            countered_id = obj

        return self.send(
            partner,
            to_partner,
            from_partner,
            message,
            countered_id=countered_id,
        )
