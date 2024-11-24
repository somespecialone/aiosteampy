!!! danger "Deprecated documentation"
    This part of the documentation is not finished yet and contains information for old versions.
    So please check the code (and docstrings) to get a better understanding of how things work.


`SteamPublicMixin` have methods that doesn't require authentication.

### Get market listings

```python
from aiosteampy import SteamPublicClient, Game

client = SteamPublicClient(...)

listings, total_count = await client.get_item_listings("★ Butterfly Knife | Slaughter (Minimal Wear)", 730)
```

### Get user inventory

```python
from aiosteampy import SteamPublicClient, Game

client = SteamPublicClient(...)

inv = await client.get_user_inventory(1234567890, Game.CSGO)

```

### Item order histogram & order activity

To do this You need an `item_name_id` value of item type.
Placed in html response `<script>` section of market item url
like `https://steamcommunity.com/market/listings/730/Revolution%20Case`.
Or You can find some in my
repo [somespecialone/steam-item-name-ids](https://github.com/somespecialone/steam-item-name-ids)

```python
from aiosteampy import SteamPublicClient

client = SteamPublicClient(...)

item_name_id = 12346789

histogram = await client.get_item_orders_histogram(item_name_id)
activity = await client.fetch_item_orders_activity(item_name_id)
```
