## Main market methods of `MarketMixin`

???+ info "Get market listings and order histogram"
    [Here](public.md)


### Get my listings

```python
from aiosteampy import SteamClient

client = SteamClient(...)

active_listings, to_confirm, but_orders = await client.get_my_listings()
```


### Place & cancel sell listing

```python
from aiosteampy import SteamClient, Game

client = SteamClient(...)

# with asset id of inventory EconItem
listing_id = await client.place_sell_listing(1234567890, Game.CSGO, price=164.57)

# with EconItem
inventory = await client.get_inventory(Game.CSGO)
listing_id = await client.place_sell_listing(inventory[0], to_receive=161.20)

# and cancel with listing id
await client.cancel_sell_listing(listing_id)

# with listing model
active_listings, _, _ = await client.get_my_listings()
await client.cancel_sell_listing(active_listings[0])
```

### Place & cancel buy order

```python
from aiosteampy import SteamClient

client = SteamClient(...)

buy_order_id = await client.place_buy_order("★ Butterfly Knife | Slaughter (Minimal Wear)", 730, price=11.51)
await client.cancel_buy_order(buy_order_id)

# with buy order model
_, _, buy_orders = await client.get_my_listings()
await client.cancel_buy_order(buy_orders[0])
```

### Buy market listing

```python
from aiosteampy import SteamClient

client = SteamClient(...)

# fetch listings
listings, total_count = await client.get_item_listings("★ Butterfly Knife | Slaughter (Minimal Wear)", 730)

wallet_info = await client.buy_market_listing(listings[0])
```
