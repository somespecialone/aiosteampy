## First words

First of all, main entity to hold all interaction with `SteamCommunity` is **client**. There are two type of **clients**:

* `SteamPublicClient` - for methods that do not require authentication, such as getting market data, listings,
  getting non-private inventory of users, etc...
* `SteamClient` - all from `SteamPublicClient` plus methods related to personal `Steam` account: login, inventory of
  self, trade offers creation, declining, countering, buying market listings, creating sell orders and more.
  _This page contains examples based on this **client**._

### Client creation, login and preparing

`SteamClient` with minimal setup, must be instantiated in **async context** (within **event loop**, or,
for simplicity, function defined with `async def`):

```python
from aiosteampy import SteamClient

client = SteamClient(
    112233,  # steam id(64) or account id(32)
    "username",
    "password",
    "shared secret",
    "identity secret",  # almost optional
    user_agent="my user agent"  # strongly recommended
)

await client.login()

# load properties required for all methods to work
# (currency, country, trade token)
await client.prepare()
```

!!! info "Prepare client to work"
    Consider preparing client to make code below work by calling `client.prepare` method after `client.login`
    or pass required properties to constructor. [Read more](./client.md)

!!! tip "User-Agent header"
    [Aiohttp](https://docs.aiohttp.org/en/stable/) uses its own `User-Agent` header by default.
    **It is strongly recommended to replace it with your own**.
    You can easily get one from [randua.somespecial.one](https://randua.somespecial.one)
    or use [User Agent Service](./ext/user_agents.md).

### Do work

Simple showcase. For more details, please, continue reading

```python
from aiosteampy import AppContext

# get self inventory
my_inventory, _, _ = await client.get_inventory(AppContext.CS2)

first_item = my_inventory[0]

# fetch listings for this item
listings, _, _ = await client.get_item_listings(first_item.description)
first_listing = listings[0]

await client.buy_market_listing(first_listing)  # buy first listing

# let's increase price for about 10%
price = int(first_listing.price * 1.1)

# place sell order on market
listing_id = await client.place_sell_listing(first_item, price=price)

# hmm, I've changed my mind and want to cancel my sell listing
await client.cancel_sell_listing(listing_id)
```

### Do another work

```python
from aiosteampy import AppContext, SteamClient

# get self inventory
inv, _, _ = await client.get_inventory(AppContext.CS2)
# get all Nova Mandrel items from inventory 
gifts = list(filter(lambda i: "Nova Mandrel" in i.description.name, inv))

partner_id = 123456789  # partner, which in friends list, id

# make and confirm trade, fetch and return trade offer
trade = await client.make_trade_offer(
    partner_id, 
    gifts, 
    message="Gift for my friend!", 
    fetch=True,
)

if trade.accepted:
    print("yeeahs")
elif trade.declined:
    print("Bbut wmhhy?")
elif trade.active:
    await client.cancel_trade_offer(trade)  # haha, I revoke my gift
```

### Catch errors

```python
from aiosteampy import App, RateLimitExceeded, EResultError

try:
    listings, _, _ = await client.get_item_listings(
        "AWP | Chromatic Aberration (Field-Tested)",
        App.CS2,
    )
except RateLimitExceeded:
    print("Whhosh, I need to rest a bit")
except EResultError as e:
    print(f"Steam response with error ({e.result}, {e.data}), what a surprise!")
```

[Dedicated exceptions chapter](./exceptions.md)

## Second words

Corresponding docs pages contain more detailed information on how to use this project, what capabilities does it have
and how things work.

Also, it is worth reading the [design page](./design.md). Check it out at least once, you won't want to miss out 😉
