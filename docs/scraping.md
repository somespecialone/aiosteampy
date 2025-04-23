# Responsible Steam Market Scraping

We all have a one, but a big and tasty, pie 🥧, called `SteamMarket`. We all want to get a piece of it 🍰,
that's why we're here. However, it's crucial to approach market data collection responsibly.

!!! danger ""
    Consume Steam resources **responsibly**.
    Bear in mind, we all benefit if Steam spends fewer resources fighting aggressive market scraping.
    Excessive scraping can lead to IP bans, rate limits, and a worse experience for everyone.

## HTTP Caching with If-Modified-Since

One of the most effective ways to scrape responsibly is to implement proper HTTP caching using the `If-Modified-Since` 
header. This standard HTTP mechanism allows clients to:

1. Retrieve data only when it has changed since the last request
2. Reduce bandwidth usage for both client and server
3. Minimize the risk of hitting rate limits
4. Create more efficient and responsive applications

### How It Works

The HTTP caching mechanism works as follows:

1. When you first request a resource, the server includes a `Last-Modified` header in the response
2. For subsequent requests, you include an `If-Modified-Since` header with the timestamp from the previous response
3. If the resource hasn't changed since that time, the server returns a `304 Not Modified` status code without the resource body
4. If the resource has changed, the server returns the updated resource with a new `Last-Modified` timestamp

In `aiosteampy`, this mechanism is implemented through the `if_modified_since` parameter and the `ResourceNotModified` exception.

## Implementation in aiosteampy

Several methods in `aiosteampy` support the `if_modified_since` parameter:

- `SteamCommunityPublicMixin.get_item_orders_histogram`
- `SteamCommunityPublicMixin.get_item_listings`
- `SteamCommunityPublicMixin.market_listings`

These methods:

1. Accept an optional `if_modified_since` parameter (either a `datetime` object or a formatted string)
2. Return a `last_modified` timestamp along with the requested data
3. Raise a `ResourceNotModified` exception when the resource hasn't changed

### Basic Example

Here's a simple example of how to use this mechanism:

```python
from aiosteampy import ResourceNotModified, SteamPublicClient

client = SteamPublicClient(...)

# Initial request to get data and last_modified timestamp
histogram, last_modified = await client.get_item_orders_histogram(123456)

# Later, when you need to check for updates
try:
    # Pass the previous last_modified timestamp
    histogram, last_modified = await client.get_item_orders_histogram(
        123456, 
        if_modified_since=last_modified,  # Use the timestamp from the previous response
    )
    # Process the updated data
    print("Data has been updated!")
    # Do something with the new histogram data
except ResourceNotModified:
    print("Data hasn't changed since last request")
    # Use your cached data instead
```

### Advanced Implementation with Caching

For a more complete implementation with caching:

```python
from aiosteampy import ResourceNotModified
import time

class SimpleCache:
    def __init__(self):
        self.data = {}
        self.timestamps = {}

    def get(self, key):
        return self.data.get(key), self.timestamps.get(key)

    def set(self, key, data, timestamp):
        self.data[key] = data
        self.timestamps[key] = timestamp

# Create a cache
cache = SimpleCache()
item_nameid = 123456

async def get_histogram_with_cache(client, item_nameid):
    # Try to get from cache
    cached_data, last_modified = cache.get(item_nameid)

    try:
        # Always make the request, but with if_modified_since if we have cached data
        histogram, new_last_modified = await client.get_item_orders_histogram(
            item_nameid,
            if_modified_since=last_modified if last_modified else None
        )

        # Update cache with new data
        cache.set(item_nameid, histogram, new_last_modified)
        return histogram

    except ResourceNotModified:
        # If data hasn't changed, use cached data
        print("Using cached data - resource not modified")
        return cached_data
```

## Benefits

Using the `If-Modified-Since` mechanism provides several benefits:

1. **Reduced Bandwidth**: You only download the full data when it has actually changed
2. **Fewer Rate Limits**: You're less likely to hit Steam's `429: Too Many Requests` errors
3. **Faster Responses**: 304 responses are faster as they don't include the resource body
4. **Server-Friendly**: Reduces load on Steam's servers, making you a good API citizen
5. **More Reliable**: Your application can continue to function even during high-traffic periods

By implementing proper caching with the `if_modified_since` parameter, you can create more efficient and 
reliable applications that interact with the Steam Market.
