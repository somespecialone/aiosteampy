"""Client for interacting with `IEconService`."""

from datetime import datetime

from ...constants import Language
from ._base import JsonResponse, SteamWebApiServiceBase

HISTORY_LIMIT = 100  # current effective limit for access token, for api key is 500


class EconServiceClient(SteamWebApiServiceBase):
    """Phone service client."""

    __slots__ = ()

    SERVICE_NAME = "IEconService"

    def get_trade_offer(
        self,
        trade_offer_id: int,
        language: Language = Language.ENGLISH,
        get_descriptions: bool = True,
    ) -> JsonResponse:
        params = {"tradeofferid": trade_offer_id, "language": language, "get_descriptions": int(get_descriptions)}
        return self._urlencoded("GetTradeOffer", params=params, auth=True)

    def get_trade_offers(
        self,
        active_only: bool = True,
        time_historical_cutoff: int | datetime | None = None,
        historical_only: bool = False,
        get_sent_offers: bool = True,
        get_received_offers: bool = True,
        get_descriptions: bool = True,
        cursor: int = 0,
        language: Language = Language.ENGLISH,
    ) -> JsonResponse:
        params = {
            "active_only": int(active_only),
            "get_sent_offers": int(get_sent_offers),
            "get_received_offers": int(get_received_offers),
            "historical_only": int(historical_only),
            "get_descriptions": int(get_descriptions),
            "cursor": cursor,
            "language": language,
        }
        if active_only and time_historical_cutoff is not None:
            if isinstance(time_historical_cutoff, datetime):
                time_historical_cutoff = int(time_historical_cutoff.timestamp())  # trunc ms
            params["time_historical_cutoff"] = time_historical_cutoff

        return self._urlencoded("GetTradeOffers", params=params, auth=True)

    def get_trade_offers_summary(self, time_last_visit: int | datetime | None = None) -> JsonResponse:
        params = None
        if time_last_visit is not None:
            if isinstance(time_last_visit, datetime):
                time_last_visit = int(time_last_visit.timestamp())
            params = {"time_last_visit": time_last_visit}

        return self._urlencoded("GetTradeOffersSummary", params=params, auth=True)

    def get_trade_status(self, trade_id: int, language: Language = Language.ENGLISH) -> JsonResponse:
        params = {"tradeid": trade_id, "get_descriptions": 1, "language": language}
        return self._urlencoded("GetTradeStatus", params=params, auth=True)

    def get_trade_history(
        self,
        max_trades: int = HISTORY_LIMIT,
        include_failed: bool = False,
        navigating_back: bool = False,
        start_after_time: int | datetime | None = None,
        start_after_trade_id: int | None = None,
        get_descriptions: bool = True,
        include_total: bool = True,
        language: Language = Language.ENGLISH,
    ) -> JsonResponse:
        params = {
            "max_trades": max_trades,
            "get_descriptions": int(get_descriptions),
            "include_total": int(include_total),
            "include_failed": int(include_failed),
            "navigating_back": int(navigating_back),
            "language": language,
        }
        if start_after_time is not None:
            if isinstance(start_after_time, datetime):
                start_after_time = int(start_after_time.timestamp())
            params["start_after_time"] = start_after_time
        if start_after_trade_id is not None:
            params["start_after_tradeid"] = start_after_trade_id

        return self._urlencoded("GetTradeHistory", params=params, auth=True)

    # with one from below we can only get inventory of current user
    # https://steamapi.xpaw.me/IEconService#GetInventoryItemsWithDescriptions
    # https://github.com/SteamTracking/Protobufs/blob/master/steam/steammessages_econ.steamclient.proto
