!!! danger "Deprecated documentation"
    This part of the documentation is not finished yet and contains information for old versions.
    So please check the code (and docstrings) to get a better understanding of how things work.


## Methods of `TradeMixin`

### Make and send trade offer

```python
from aiosteampy import SteamClient, Game

client = SteamClient(...)

inv = await client.get_inventory(Game.CSGO)

partner_steam_id = 123456
partner_inv = await client.get_user_inventory(partner_steam_id, Game.CSGO)

offer_id = await client.make_trade_offer(partner_steam_id, [inv[0]], [partner_inv[0]], 'Hi, lets change our items!')
```

### Get offer from Steam and check if offer is accepted

```python
from aiosteampy import TradeOfferStatus

offer = await client.get_trade_offer(offer_id)

offer.status == TradeOfferStatus.ACCEPTED
```

### Get offers from Steam and counter one, accept & cancel

```python
from aiosteampy import SteamClient, Game

client = SteamClient(...)

sent_offers, received_offers = await client.get_trade_offers()

await client.counter_trade_offer(received_offers[0], to_receive=[], message='I want this to be a gift!')

await client.accept_trade_offer(received_offers[1])

await client.cancel_trade_offer(received_offers[2])
```
