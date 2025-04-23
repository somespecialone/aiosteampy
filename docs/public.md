# Public API Methods

!!! warning "Rate Limiting"
    Many methods in this section are rate-limited by Steam. 
    Making too many requests in a short period of time can result in temporary bans. 
    Always implement proper rate limiting and caching in your application to avoid being banned. 
    Take a look at the [scraping](./scraping.md) page for more information.
    Methods that are rate-limited are marked with ⚠️.

The `SteamCommunityPublicMixin` class provides methods that don't require authentication. 
These methods are available through the `SteamPublicClient` class.

## User Inventory

Get a user's inventory for a specific app and context:

```python
from aiosteampy import SteamPublicClient, AppContext

client = SteamPublicClient()

# Get a user's inventory by Steam ID
inventory, _, _ = await client.get_user_inventory(1234567890, AppContext.CS2)

# Iterate through inventory items
for item in inventory:
    print(f"Item: {item.description.market_hash_name}, Asset ID: {item.asset_id}")
```

You can also use the async iterator version:

```python
async for inventory, _, _ in client.user_inventory(1234567890, AppContext.CS2):
    for item in inventory:
        print(f"Item: {item.description.market_hash_name}, Asset ID: {item.asset_id}")
```

To find a specific item in a user's inventory:

```python
# Find by asset ID
item = await client.get_user_inventory_item(1234567890, AppContext.CS2, 12345678901)

# Find using a custom predicate function
item = await client.get_user_inventory_item(1234567890, AppContext.CS2, lambda i: "Knife" in i.market_hash_name)
```

## Market Listings ⚠️

Get market listings for a specific item:

```python
from aiosteampy import SteamPublicClient, App

client = SteamPublicClient()

# Get listings for an item by name and app ID
listings, total_count, last_modified = await client.get_item_listings("★ Butterfly Knife | Slaughter (Minimal Wear)", App.CS2)

# Print listing details
for listing in listings:
    print(f"Listing ID: {listing.id}, Skin: {listing.item.description.market_name}, Price: {listing.price}")
```

You can also use the async iterator version:

```python
async for listings, _, _ in client.market_listings("★ Butterfly Knife | Slaughter (Minimal Wear)", App.CS2):
    for listing in listings:
        print(f"Listing ID: {listing.id}, Skin: {listing.item.description.market_name}, Price: {listing.price}")
```

!!! note
    The `get_item_listings` method accepts an `if_modified_since` parameter and returns a `last_modified` timestamp to help with rate limiting. See [scraping](./scraping.md) for more information on how to use this mechanism effectively.

## Finding Item Name ID ⚠️

The item_name_id is required for some methods. You can get it using:

```python
from aiosteampy import SteamPublicClient, App

client = SteamPublicClient()

# Get item_name_id by item name and app ID
item_name_id = await client.get_item_name_id("Revolution Case", App.CS2)
print(f"Item name ID: {item_name_id}")
```

You can also find item name IDs in the HTML of market pages or in repositories like [somespecialone/steam-item-name-ids](https://github.com/somespecialone/steam-item-name-ids).

## Item Order Histogram ⚠️

Get buy and sell order data for an item:

```python
from aiosteampy import SteamPublicClient, App

client = SteamPublicClient()

# You need the item_name_id value, which can be found in the HTML of the market page
# or by using the get_item_name_id method
item_name_id = await client.get_item_name_id("Revolution Case", App.CS2)

# Get order histogram data
histogram, last_modified = await client.get_item_orders_histogram(item_name_id)

# Access buy and sell orders
print(f"Highest buy order: {histogram.highest_buy_order}")
print(f"Lowest sell order: {histogram.lowest_sell_order}")

# Iterate through buy orders
for order in histogram.buy_order_table:
    print(f"Buy order: {order.price}, Quantity: {order.quantity}")

# Iterate through sell orders
for order in histogram.sell_order_table:
    print(f"Sell order: {order.price}, Quantity: {order.quantity}")
```

!!! note
    The `get_item_orders_histogram` method accepts an `if_modified_since` parameter and returns a `last_modified` timestamp to help with rate limiting. See [scraping](./scraping.md) for more information on how to use this mechanism effectively.

## Item Orders Activity

Get recent order activity for an item:

```python
from aiosteampy import SteamPublicClient, App

client = SteamPublicClient()

# Get item_name_id first
item_name_id = await client.get_item_name_id("Revolution Case", App.CS2)

# Get order activity
activity = await client.fetch_item_orders_activity(item_name_id)

# Print activity details
for entry in activity["activity"]:
    print(f"Type: {entry['type']}, Price: {entry['price']}, Time: {entry['time']}")
```

## Price Overview

Get a price overview for an item:

```python
from aiosteampy import SteamPublicClient, App

client = SteamPublicClient()

# Get price overview by item name and app ID
price_overview = await client.fetch_price_overview("AK-47 | Redline (Field-Tested)", App.CS2)

# Print price information
print(f"Lowest price: {price_overview['lowest_price']}")
print(f"Median price: {price_overview['median_price']}")
print(f"Volume: {price_overview['volume']}")
```

## Market Search ⚠️

Search for items on the Steam Community Market:

```python
from aiosteampy import SteamPublicClient, App

client = SteamPublicClient()

# Search for items with basic parameters
results, total_count = await client.get_market_search_results(
    query="Knife",  # Search query
    app=App.CS2,    # Game/app to search in
    count=10,       # Number of results to return
    descriptions=True,  # Include descriptions in search
    sort_column="price",  # Sort by price
    sort_dir="asc"       # Sort in ascending order
)

# Print search results
for item in results:
    print(f"Item: {item.description.market_name}, Price: {item.sell_price}")
    print(f"Quantity: {item.sell_listings}")
```

You can also use the async iterator version to paginate through results:

```python
async for results, total_count in client.market_search_results("Knife", App.CS2):
    for item in results:
        print(f"Item: {item.description.market_name}, Price: {item.sell_price}")
```

### Get Market Search Filters

You can retrieve the available filters for a specific app:

```python
from aiosteampy import SteamPublicClient, App

client = SteamPublicClient()

# Get available filters for CS2
filters = await client.get_market_search_app_filters(App.CS2)

# Print filter categories
for category, option in filters.items():
    print(f"Category: {category}")
    print(f"Option: {option['name']}")
    for tag_key, tag_data in option["tags"].items():
        print(f"Tag: {tag_data['localized_name']}")
```

### Filters Example

You can use filters to narrow down your search results. 
Filters are specified as a dictionary where keys are filter categories and values are filter options.

Example for CS2, searching for items from "The Anubis Collection":

```python
from aiosteampy import SteamPublicClient, App

client = SteamPublicClient()

# Search with a single filter
results, total_count = await client.get_market_search_results(
    app=App.CS2, 
    filters={"category_730_ItemSet[]": "tag_set_anubis"}
)

# Search with multiple filters (e.g., Anubis Collection + Covert Rarity)
results, total_count = await client.get_market_search_results(
    app=App.CS2, 
    filters={
        "category_730_ItemSet[]": "tag_set_anubis",
        "category_730_Rarity[]": "tag_Rarity_Ancient_Weapon"
    }
)

# Search with multiple values for the same filter (e.g., multiple collections)
results, total_count = await client.get_market_search_results(
    app=App.CS2, 
    filters={
        "category_730_ItemSet[]": ["tag_set_anubis", "tag_set_op10"]
    }
)
```

You can find filter values by using the `get_market_search_app_filters` method or by inspecting the network requests 
in your browser when using the Steam Market's advanced search options.
