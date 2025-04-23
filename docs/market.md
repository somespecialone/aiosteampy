# Steam Market Methods

The `MarketMixin` class provides methods for interacting with the Steam Market. 
These methods require authentication and are available through the `SteamClient` class.

!!! warning "Financial Responsibility"
    Using these methods involves real money transactions. 
    Always double-check prices and quantities before executing market operations. 
    The library authors are not responsible for any financial losses that may occur.

## Getting Market Information

### Get My Listings

Retrieve your active market listings, listings awaiting confirmation, and active buy orders:

```python
from aiosteampy import SteamClient

client = SteamClient(...)
await client.login()

# Get all your listings
active_listings, to_confirm, buy_orders, total_count = await client.get_my_listings()

# Print active listings
for listing in active_listings:
    print(f"Listing ID: {listing.listing_id}, Item: {listing.item.description.market_name}, Price: {listing.price}")

# Print listings awaiting confirmation
for listing in to_confirm:
    print(f"Listing to confirm: {listing.item.description.market_name}, Price: {listing.price}")

# Print buy orders
for order in buy_orders:
    print(f"Buy Order ID: {order.buy_order_id}, Item: {order.item_description.market_hash_name}, Price: {order.price}")
```

You can also use the async iterator version to iterate over your **active listings**:

```python
async for active_listings in client.my_listings():
    for listing in active_listings:
        # Process listings
        pass
```

### Get My Market History

Retrieve your market transaction history:

```python
from aiosteampy import SteamClient
from aiosteampy.models import MarketHistoryEventType

client = SteamClient(...)
await client.login()

# Get market history
events, total_count = await client.get_my_market_history()

# Print market history events
for event in events:
    if event.type == MarketHistoryEventType.LISTING_PURCHASED:
        print(f"Purchased: {event.listing.item.description.market_hash_name} for {event.listing.price}")
    elif event.type == MarketHistoryEventType.LISTING_SOLD:
        print(f"Sold: {event.listing.item.description.market_hash_name} for {event.listing.price}")
```

You can also use the async iterator version:

```python
async for events, total_count in client.my_market_history():
    # Process history
    for event in events:
        pass
```

### Get Wallet Information

Check your Steam wallet balance and market eligibility:

```python
from aiosteampy import SteamClient

client = SteamClient(...)
await client.login()

# Get wallet info
wallet_info = await client.get_wallet_info()
print(f"Balance: {wallet_info['wallet_balance']}")
print(f"Currency: {wallet_info['wallet_currency']}")

# Check if market is available
is_available = await client.is_market_available()
print(f"Market available: {is_available}")
```

## Selling Items

### Place Sell Listing

List an item from your inventory for sale on the market:

```python
from aiosteampy import SteamClient, AppContext

client = SteamClient(...)
await client.login()

# Get your inventory
inventory, _, _ = await client.get_inventory(AppContext.CS2)

# Method 1: Sell using an EconItem object with price
listing_id = await client.place_sell_listing(inventory[0], price=10000)  # Price in cents (100.00)

# Method 2: Sell using an EconItem object with desired amount to receive
listing_id = await client.place_sell_listing(inventory[0], to_receive=8700)  # Amount to receive after fees

# Method 3: Sell using asset ID with price
listing_id = await client.place_sell_listing(1234567890, AppContext.CS2, price=10000)

# Method 4: Sell using asset ID with desired amount to receive
listing_id = await client.place_sell_listing(1234567890, AppContext.CS2, to_receive=8700)

# Fetch the listing after creation
listing = await client.place_sell_listing(inventory[0], price=10000, fetch=True)
print(f"Created listing: {listing.listing_id}, Price: {listing.price}")
```

### Cancel Sell Listing

Cancel an active sell listing:

```python
from aiosteampy import SteamClient

client = SteamClient(...)
await client.login()

# Method 1: Cancel using listing ID
await client.cancel_sell_listing(1234567890)

# Method 2: Cancel using listing object
active_listings, _, _, _ = await client.get_my_listings()
if active_listings:
    await client.cancel_sell_listing(active_listings[0])

# Find and cancel a specific listing
listing = await client.get_my_sell_listing(market_hash_name="AK-47 | Redline (Field-Tested)")
if listing:
    await client.cancel_sell_listing(listing)
```

## Buying Items

### Place Buy Order

Create a buy order for an item:

```python
from aiosteampy import SteamClient, App

client = SteamClient(...)
await client.login()

# Method 1: Place buy order using item name and app ID
buy_order_id = await client.place_buy_order("AK-47 | Redline (Field-Tested)", App.CS2, price=1000, quantity=1)

# Method 2: Place buy order for multiple items
buy_order_id = await client.place_buy_order("Revolution Case", App.CS2, price=50, quantity=10)

# Fetch the buy order after creation
buy_order = await client.place_buy_order("AK-47 | Redline (Field-Tested)", App.CS2, price=1000, fetch=True)
print(f"Created buy order: {buy_order.buy_order_id}, Price: {buy_order.price}")
```

### Cancel Buy Order

Cancel an active buy order:

```python
from aiosteampy import SteamClient

client = SteamClient(...)
await client.login()

# Method 1: Cancel using buy order ID
await client.cancel_buy_order(1234567890)

# Method 2: Cancel using buy order object
_, _, buy_orders, _ = await client.get_my_listings()
if buy_orders:
    await client.cancel_buy_order(buy_orders[0])

# Find and cancel a specific buy order
buy_order = await client.get_my_buy_order(market_hash_name="AK-47 | Redline (Field-Tested)")
if buy_order:
    await client.cancel_buy_order(buy_order)
```

### Buy Market Listing

Purchase an item directly from a market listing:

```python
from aiosteampy import SteamClient, App

client = SteamClient(...)
await client.login()

# Method 1: Buy using a listing object
listings, _ = await client.get_item_listings("AK-47 | Redline (Field-Tested)", App.CS2)
if listings:
    wallet_info = await client.buy_market_listing(listings[0])
    print(f"New wallet balance: {wallet_info['wallet_balance']}")

# Method 2: Buy using listing ID, price, and item details
wallet_info = await client.buy_market_listing(
    1234567890,  # Listing ID
    price=1000,  # Price in cents
    market_hash_name="AK-47 | Redline (Field-Tested)",
    app=App.CS2
)
```

## Price History

Get historical price data for an item:

```python
from aiosteampy import SteamClient, App

client = SteamClient(...)
await client.login()

# Get price history for an item
price_history = await client.fetch_price_history("AK-47 | Redline (Field-Tested)", App.CS2)

# Print price history entries
for entry in price_history:
    print(f"Date: {entry.date}, Price: {entry.price}, Volume: {entry.daily_volume}")
```

## Market Availability

Check if the market is available and get market restrictions:

```python
from aiosteampy import SteamClient

client = SteamClient(...)
await client.login()

# Check if market is available
is_available = await client.is_market_available()

# Get more detailed market availability info
is_available, when = await client.get_market_availability_info()
```
