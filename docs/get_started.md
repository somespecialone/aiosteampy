{%
include-markdown "../README.md"
start="<!--usage-start-->"
end="<!--usage-end-->"
%}

#### Public

`SteamPublicClient` encompasses all domain methods that can be done without a need to be authenticated.
Smiply, it allows us to interact with `Steam` domains without a need to do a login:

```python
import asyncio

from aiosteampy.client import SteamPublicClient, App


async def get_market_listings():
    client = SteamPublicClient()

    listings = await client.market.get_listings(
        "FAMAS | Rapid Eye Movement (Field-Tested)",
        App.CS2,
    )

    print(listings.listings)


asyncio.run(get_market_listings())
```

Fetching price history of an item works similarly — no login needed:

```python
import asyncio

from aiosteampy.client import SteamPublicClient, App


async def get_price_history():
    client = SteamPublicClient()

    entries = await client.market.get_price_history(
        "Collector's Bonk! Atomic Punch",
        App.TF2,
    )

    for e in entries:
        print(e.date, e.price_raw, e.daily_volume)


asyncio.run(get_price_history())
```

Each `PriceHistoryEntry` contains:

- `price` — price in cents (`int`)
- `price_raw` — raw price as returned by Steam (`float`)
- `date` — sale date (`datetime`)
- `daily_volume` — number of sales on that day (`int`)

An empty list is returned when Steam has no history for the item.

## More examples

Below are more comprehensive examples to help understand how things work.

### Do work

```python
from aiosteampy.client import SteamClient, AppContext

client = SteamClient(...)

# get inventory of the current user
my_inventory = await client.inventory.get(AppContext.CS2)
first_item = my_inventory.items[0]

# fetch listings for this item class
listings = await client.market.get_listings(first_item.description)
first_listing = listings.listings[0]

# buy first listing
wallet_info = await client.market.buy_listing(first_listing)
print("Remaining balance: ", wallet_info.balance)

# let's increase price for about 20%
my_price = int(first_listing.converted.price * 1.2)

# place sell order on a market
listing_id = await client.market.place_sell_listing(first_item, price=my_price)

# hmm, we've changed our idea and want to cancel sell listing
await client.market.cancel_sell_listing(listing_id)
```

### Do another work

```python
from aiosteampy.client import SteamClient, AppContext
from aiosteampy.id import SteamID

client = SteamClient(...)

# get inventory of the current user
my_inventory = await client.inventory.get(AppContext.CS2)
# get all Nova Mandrel items from inventory 
gifts = list(filter(lambda i: "Nova Mandrel" in i.description.name, my_inventory.items))

partner = SteamID(123456789)  # partner, which is in a friends list

# make and confirm trade, fetch and return trade offer
trade_offer_id = await client.trade.send(
    partner,
    gifts,
    message="Gift for my friend!",
)

trade = await client.trade.get(trade_offer_id)

# wait some time to give partner a time to react

if trade.accepted:
    print("yeeahs")
elif trade.declined:
    print("Bbut wmhhy?")
elif trade.active:
    await client.trade.cancel(trade)  # haha, we revoke our gift
```

### Catch errors

```python
from aiosteampy.client import SteamClient, EResultError
from aiosteampy.transport import NetworkError

client = SteamClient(...)

try:
    await client.profile.set_alias("my_awesome_alias")
    notifications = await client.notifications.get()
except NetworkError:
    print("Need to pay my internet bills :(")
except EResultError as e:
    print(f"Steam response with error ({e.result} | {e.msg} | {e.data}), what a surprise!")
```

[//]: # (!!!info "Exceptions")

[//]: # (    [Dedicated exceptions chapter]&#40;./exceptions.md&#41;)
