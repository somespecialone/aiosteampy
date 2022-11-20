This is the example of how to override methods(hooks) to cache data in memory on instance attrs.

Caching and removing from cache `confirmations` work fine, but, unfortunately, there is pitfalls with `tradeoffers`.
There is no way to handle full lifecycle of `tradeoffers` without periodically poll changes from `steam web api` 
(good one idea is for trigger filling trades with [get_notifications](https://github.com/somespecialone/aiosteampy/blob/master/aiosteampy/client.py)
client method).

> But I hope I do some of this in near future in other project which will be more suitable for trading and be middle-high layer over of and based on this project
> like [DoctorMcKay/node-steam-tradeoffer-manager](https://github.com/DoctorMcKay/node-steam-tradeoffer-manager) on 
> [DoctorMcKay/node-steam-user](https://github.com/DoctorMcKay/node-steam-user).

Or not, who knows 😶

!!! tip "Where is hooks"
    To see where hooks were called check [TradeMixin](https://github.com/somespecialone/aiosteampy/blob/master/aiosteampy/trade.py)
    and [ConfirmationMixin](https://github.com/somespecialone/aiosteampy/blob/master/aiosteampy/confirmation.py)

```python
from typing import TypeAlias, Callable

from aiosteampy.constants import ConfirmationType
from aiosteampy.models import Confirmation, TradeOffer

PRED_C: TypeAlias = Callable[[Confirmation], bool]
PRED_T: TypeAlias = Callable[[TradeOffer], bool]

STORAGE_TRADES_KEY = "trades"
STORAGE_LISTINGS_KEY = "listings"


class StatesMixin:
    """States."""

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
```