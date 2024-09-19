We all have a one, but a big and tasty, pie 🥧, called `SteamMarket`. We all want to get a piece of it 🍰,
that's why we're here.
So the general idea is:

!!! warning ""
    Consume Steam resources **responsibly**.
    Bear in mind, we all benefit if `Steam` spends fewer resources fighting aggressive market scraping


## And what do you propose?

Use `If-Modified-Since` header with timestamp for each request, where it is possible!

For instance:

```python
from aiosteampy import ResourceNotModified

# get initial data
histogram, last_modified = await client.get_item_orders_histogram(123456)

try:
    histogram, last_modified = await client.get_item_orders_histogram(
        123456, 
        if_modified_since=last_modified,  # right there
    )
except ResourceNotModified:
    print(
        "There we handle old data with some cache implementation",
        "Or do nothing depending on your business logic",
    )
```

`ResourceNotModified` exception will be raised in case when **client** receive **304** status code.
Moreover, you will definitely get less `429: Too Many Requests` status codes and other errors from `Steam`!

### Where it is possible

- _SteamCommunityPublicMixin.get_item_orders_histogram_
- _SteamCommunityPublicMixin.get_item_listings_
- _SteamCommunityPublicMixin.market_listings_
