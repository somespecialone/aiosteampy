# Steam Trade Methods

The `TradeMixin` class provides methods for interacting with Steam Trades. 
These methods require authentication and are available through the `SteamClient` class.

!!! warning "Trade Responsibility"
    Trading items involves transferring potentially valuable virtual items. 
    Always verify trade contents before confirming trades. 
    The library authors are not responsible for any losses that may occur

## Getting Trade Information

### Get Trade Offers

Retrieve your active trade offers:

```python
from aiosteampy import SteamClient

client = SteamClient(...)
await client.login()

# Get all trade offers (both sent and received)
sent_offers, received_offers, next_cursor = await client.get_trade_offers()

# Print sent offers
for offer in sent_offers:
    print(f"Offer ID: {offer.id}, Partner: {offer.partner_id}, Status: {offer.status}")
    print(f"Items to give: {len(offer.items_to_give)}, Items to receive: {len(offer.items_to_receive)}")

# Print received offers
for offer in received_offers:
    print(f"Offer ID: {offer.id}, Partner: {offer.partner_id}, Status: {offer.status}")
    print(f"Items to give: {len(offer.items_to_give)}, Items to receive: {len(offer.items_to_receive)}")
```

You can also use the async iterator version:

```python
async for sent_offers, received_offers, _ in client.trade_offers():
    # Process offers
    pass
```

### Get Specific Trade Offer

Retrieve a specific trade offer by ID:

```python
from aiosteampy import SteamClient, TradeOfferStatus

client = SteamClient(...)
await client.login()

# Get a specific trade offer
offer_id = 1234567890
offer = await client.get_trade_offer(offer_id)

# Check offer status
if offer.status is TradeOfferStatus.ACTIVE:
    print("Offer is active")
elif offer.status is TradeOfferStatus.ACCEPTED:
    print("Offer has been accepted")
elif offer.status is TradeOfferStatus.DECLINED:
    print("Offer has been declined")
elif offer.status is TradeOfferStatus.CANCELED:
    print("Offer has been canceled")
elif offer.status is TradeOfferStatus.INVALID_ITEMS:
    print("Offer contains invalid items")
```

### Get Trade History

Retrieve your trade history:

```python
from aiosteampy import SteamClient

client = SteamClient(...)
await client.login()

# Get trade history
trades, total_history_trades = await client.get_trade_history()

# Print trade history
for trade in trades:
    print(f"Trade ID: {trade.id}, Partner: {trade.partner_id}")
    print(f"Assets given: {len(trade.assets_given)}, Assets received: {len(trade.assets_received)}")
    print(f"Time initiated: {trade.time_init}")
```

### Get Trade Offers Summary

Get a summary of your trade offers:

```python
from aiosteampy import SteamClient

client = SteamClient(...)
await client.login()

# Get trade offers summary
summary = await client.get_trade_offers_summary()

# Print summary
print(f"Pending received offers: {summary['pending_received_count']}")
print(f"New received offers: {summary['new_received_count']}")
print(f"Updated received offers: {summary['updated_received_count']}")
print(f"Historical received offers: {summary['historical_received_count']}")
print(f"Pending sent offers: {summary['pending_sent_count']}")
print(f"Historical sent offers: {summary['historical_sent_count']}")
```

## Creating Trade Offers

### Make a Trade Offer

Create and send a trade offer to another user:

```python
from aiosteampy import SteamClient, AppContext

client = SteamClient(...)
await client.login()

# Get your inventory
your_inventory, _, _ = await client.get_inventory(AppContext.CS2)

# Get partner's inventory
partner_steam_id = 1234567890
partner_inventory, _, _ = await client.get_user_inventory(partner_steam_id, AppContext.CS2)

# Method 1: Create a trade offer with items from both sides
offer_id = await client.make_trade_offer(
    partner_steam_id,
    to_give=[your_inventory[0]],  # Items you're giving
    to_receive=[partner_inventory[0]],  # Items you're receiving
    message="Let's trade these items!"
)

# Method 2: Create a gift (only giving items)
offer_id = await client.make_trade_offer(
    partner_steam_id,
    to_give=[your_inventory[1]],
    to_receive=[],  # Empty list means you're not receiving anything
    message="Here's a gift for you!"
)

# Method 3: Create a trade offer using a trade URL
trade_url = "https://steamcommunity.com/tradeoffer/new/?partner=123456789&token=abcdef123456"
offer_id = await client.make_trade_offer(
    trade_url,
    to_give=[your_inventory[2]],
    to_receive=[partner_inventory[1]],
    message="Trading via URL"
)

# Fetch the offer after creation
offer = await client.make_trade_offer(
    partner_steam_id,
    to_give=[your_inventory[3]],
    to_receive=[partner_inventory[2]],
    message="Let's trade!",
    fetch=True
)
print(f"Created offer: {offer.id}, Status: {offer.status}")
```

## Managing Trade Offers

### Accept a Trade Offer

Accept a trade offer you've received:

```python
from aiosteampy import SteamClient

client = SteamClient(...)
await client.login()

# Method 1: Accept using offer ID
await client.accept_trade_offer(1234567890)

# Method 2: Accept using offer object
_, received_offers, _ = await client.get_trade_offers()
if received_offers:
    await client.accept_trade_offer(received_offers[0])
```

### Decline a Trade Offer

Decline a trade offer you've received:

```python
from aiosteampy import SteamClient

client = SteamClient(...)
await client.login()

# Method 1: Decline using offer ID
await client.decline_trade_offer(1234567890)

# Method 2: Decline using offer object
_, received_offers, _ = await client.get_trade_offers()
if received_offers:
    await client.decline_trade_offer(received_offers[0])
```

### Cancel a Trade Offer

Cancel a trade offer you've sent:

```python
from aiosteampy import SteamClient

client = SteamClient(...)
await client.login()

# Method 1: Cancel using offer ID
await client.cancel_trade_offer(1234567890)

# Method 2: Cancel using offer object
sent_offers, _, _ = await client.get_trade_offers()
if sent_offers:
    await client.cancel_trade_offer(sent_offers[0])
```

### Counter a Trade Offer

Counter a trade offer with your own terms:

```python
from aiosteampy import SteamClient, AppContext

client = SteamClient(...)
await client.login()

# Get your inventory
your_inventory, _, _ = await client.get_inventory(AppContext.CS2)

# Get received offers
_, received_offers, _ = await client.get_trade_offers()
if received_offers:
    # Method 1: Counter using offer object
    await client.counter_trade_offer(
        received_offers[0],
        to_give=[your_inventory[0]],  # What you're giving
        to_receive=[],  # What you're receiving
        message="Here's my counter offer"
    )

    # Method 2: Counter using offer ID and partner ID
    await client.counter_trade_offer(
        1234567890,  # Offer ID
        to_give=[your_inventory[1]],
        to_receive=[],
        message="Counter offer",
        partner_id=76561198123456789  # Partner's Steam ID
    )
```

## Trade Receipt

Get details of a completed trade:

```python
from aiosteampy import SteamClient

client = SteamClient(...)
await client.login()

# Get trade receipt
receipt = await client.get_trade_receipt(1234567890)

# Print receipt details
for item in receipt.assets_given:
    print(f"Given item: {item.description.market_name}, Asset ID: {item.asset_id}")
```
