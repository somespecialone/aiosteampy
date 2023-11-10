### Client creation and login

`SteamClient` with minimal setup:

```python
from aiosteampy import SteamClient


client = SteamClient(
    "username",
    "password",
    112233,  # steam id(64) or account id(32)
    shared_secret="shared secret",
    identity_secret="identity secret",
    user_agent="my user agent :)"
)

await client.login()
```

??? info "Client args"
    Client will retrieve needed data from `steam` if you not pass it. Details [there](client.md#init--login).

???+ tip "User-Agent"
    [Aiohttp](https://docs.aiohttp.org/en/stable/) uses its own `User-Agent` header by default.
    It is strongly recommended to replace it with your own.
    You can easily get one from [randua.somespecial.one](https://randua.somespecial.one).

### Do work

```python
from aiosteampy import Game


inv = await client.get_inventory(Game.CSGO)  # get self inventory

listings, total_count = await client.get_item_listings(inv[0])  # fetch listings for this item

wallet_balance = await client.buy_market_listing(listings[0])  # buy first listing and get new wallet balance

listing_id = await client.place_sell_listing(inv[0], price=15.6)  # place sell order on market

await client.cancel_sell_listing(listing_id)  # changed my mind and want to cancel my sell listing
```

### Do another work

```python
from aiosteampy import Game, TradeOfferStatus


gifts = await client.get_inventory(Game.CSGO, predicate=lambda i: "Nova Mandrel" in i.class_.name)  # get all Nova Mandrel items from inventory 

partner_id = 123456789  # in friends list
offer_id = await client.make_trade_offer(partner_id, gifts, message="Gift for my friend!")  # make and confirm trade

gift_trade = await client.fetch_trade(offer_id)  # just get trade from steam
if gift_trade.status is TradeOfferStatus.ACCEPTED:
    print("yeeah")
elif gift_trade.status is TradeOfferStatus.DECLINED:
    print("Ouugh noo...")
```
