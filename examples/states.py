from typing import TypeAlias, Callable

from aiosteampy.constants import ConfirmationType
from aiosteampy.models import Confirmation, TradeOffer

PRED_C: TypeAlias = Callable[[Confirmation], bool]
PRED_T: TypeAlias = Callable[[TradeOffer], bool]

STORAGE_TRADES_KEY = "trades"
STORAGE_LISTINGS_KEY = "listings"


class StatesMixin:
    """
    In-memory states mixin.
    Not memory safe. Flush cache periodically.
    """

    __slots__ = ()
    _confirmation_storage: dict[str, dict[str | int, Confirmation]]  # listing/trade id/ident code
    _trades_storage: dict[int, TradeOffer]

    def __init__(self, *args, **kwargs):
        self._confirmation_storage = {
            STORAGE_TRADES_KEY: {},
            STORAGE_LISTINGS_KEY: {},
        }
        self._trades_storage = {}

        super().__init__(*args, **kwargs)

    async def remove_confirmation(self, id_or_ident: str | int, conf: Confirmation):
        if conf.type is ConfirmationType.LISTING:
            self._confirmation_storage[STORAGE_LISTINGS_KEY].pop(id_or_ident, None)
        else:
            self._confirmation_storage[STORAGE_TRADES_KEY].pop(conf.creator_id, None)

    async def remove_multiple_confirmations(self, conf_ids: list[int | str], confs: list[Confirmation]):
        for index, id_or_ident in enumerate(conf_ids):
            conf = confs[index]
            if conf.type is ConfirmationType.LISTING:
                self._confirmation_storage[STORAGE_LISTINGS_KEY].pop(id_or_ident, None)
            else:
                self._confirmation_storage[STORAGE_TRADES_KEY].pop(conf.creator_id, None)

    async def store_multiple_confirmations(self, conf_ids: list[int | str], confs: list[Confirmation]):
        for index, id_or_ident in enumerate(conf_ids):
            conf = confs[index]
            if conf.type is ConfirmationType.LISTING:
                self._confirmation_storage[STORAGE_LISTINGS_KEY][id_or_ident] = conf
            elif conf.type is ConfirmationType.TRADE:
                self._confirmation_storage[STORAGE_TRADES_KEY][id_or_ident] = conf
            # unknown type going away

    async def get_confirmation(self, id_or_ident: str | int) -> Confirmation | None:
        return self._confirmation_storage[STORAGE_TRADES_KEY].get(id_or_ident) or self._confirmation_storage[
            STORAGE_LISTINGS_KEY
        ].get(id_or_ident)

    async def get_confirmations(self, predicate: PRED_C = None) -> list[Confirmation]:
        confs = [*self._confirmation_storage[STORAGE_TRADES_KEY], *self._confirmation_storage[STORAGE_LISTINGS_KEY]]
        return [c for c in confs if predicate(c)] if predicate else confs

    async def remove_trade_offer(self, offer_id: int, offer: TradeOffer | None):
        self._trades_storage.pop(offer_id, None)

    async def store_trade_offer(self, offer_id: int, offer: TradeOffer):
        self._trades_storage[offer_id] = offer

    async def store_multiple_trade_offers(self, offer_ids: list[int], offers: list[TradeOffer]):
        for index, offer_id in enumerate(offer_ids):
            self._trades_storage[offer_id] = offers[index]

    async def get_trade_offer(self, offer_id: int) -> TradeOffer | None:
        return self._trades_storage.get(offer_id)

    async def get_trade_offers(self, predicate: PRED_T = None) -> list[TradeOffer]:
        trades = self._trades_storage.values()
        return [t for t in trades if predicate(t)] if predicate else list(trades)
