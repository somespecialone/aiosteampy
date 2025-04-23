# Exception Handling

This library uses a structured exception hierarchy to help you handle different types of errors that may occur when 
interacting with the Steam API. Each method's docstring specifies which exceptions it may raise.

## Exception Hierarchy

All Steam-related errors inherit from the base `SteamError` class. This allows you to catch all Steam-specific errors 
with a single exception handler:

```python
from aiosteampy import SteamClient, SteamError, AppContext

client = SteamClient(...)

try:
    await client.login()
    await client.get_inventory(AppContext.CS2)
except SteamError as e:
    print(f"A Steam error occurred: {e}")
    # Handle the error appropriately
```

## Specific Exception Types

For more granular error handling, you can catch specific exception types:

### EResultError

Raised when Steam responds with an error code in the `success` field of a JSON response. These errors correspond to 
Steam's internal error codes.

```python
from aiosteampy import SteamClient, EResultError, App, EResult

client = SteamClient(...)

try:
    await client.place_buy_order("AK-47 | Redline (Field-Tested)", App.CS2, price=1000)
except EResultError as e:
    print(f"Steam returned an error: {e}")
    print(f"Error code: {e.result}")

    # Handle specific error codes
    if e.result is EResult.FAIL:  # EResult.Fail
        print("The operation failed")
    elif e.result is EResult.ACCESS_DENIED:  # EResult.AccessDenied
        print("Access denied - you may need to login again")
    elif e.result is EResult.INSUFFICIENT_FUNDS:  # EResult.InsufficientFunds
        print("You don't have enough funds for this purchase")
```

For a complete list of error codes and their meanings, visit [steamerrors.com](https://steamerrors.com).

### LoginError

Raised when there's an error during the login process. This could be due to incorrect credentials, Steam Guard issues, 
or other authentication problems.

```python
from aiosteampy import SteamClient, LoginError

client = SteamClient(...)

try:
    await client.login()
except LoginError as e:
    print(f"Login failed: {e}")
```

### SessionExpired

Raised when your session with Steam has expired. This is determined solely by Steam's response, not by any internal 
logic like checking the `access_token`.

```python
from aiosteampy import SteamClient, AppContext, SessionExpired

client = SteamClient(...)
await client.login()

try:
    await client.get_inventory(AppContext.CS2)
except SessionExpired as e:
    print(f"Session expired: {e}")

    # Re-login and try again
    await client.login()
    inventory, total_count, last_asset_id = await client.get_inventory(AppContext.CS2)
```

### RateLimitExceeded

Raised when you've been rate limited by Steam. This happens when you make too many requests in a short period of time.

!!! info "Retry after"
    Steam does not provide information about how long you need to wait before making new requests - you'll need to
    implement your own backoff strategy

```python
from aiosteampy import SteamClient,App, RateLimitExceeded
import asyncio

client = SteamClient(...)
await client.login()

try:
    # Making many requests in a loop might trigger rate limiting (got you banned almost instantly)
    for i in range(100):
        await client.get_item_listings("AK-47 | Redline (Field-Tested)", App.CS2)
except RateLimitExceeded as e:
    print(f"Rate limited: {e}")

    # Wait before trying again (duration is arbitrary since Steam doesn't specify it)
    print("Waiting 60 seconds before trying again...")
    await asyncio.sleep(60)

    # Try again with a slower rate (got you banned soon)
    for i in range(100):
        await client.get_item_listings("AK-47 | Redline (Field-Tested)", App.CS2)
        await asyncio.sleep(1)  # Add delay between requests
```

See [Scraping Documentation](./scraping.md) for more information on handling rate limits.

### ResourceNotModified

Raised when the requested data hasn't changed since the timestamp specified in the `If-Modified-Since` header. 
This is useful for caching, reducing unnecessary data transfer, and most importantly, reducing the risk of **being 
banned** by Steam.

```python
from datetime import datetime, timedelta

from aiosteampy import SteamClient, ResourceNotModified

client = SteamClient(...)
await client.login()

# Get current time
now = datetime.now()

try:
    # Try to get data with If-Modified-Since header
    histogram, last_modified = await client.get_item_orders_histogram(
        12345678,  # item_name_id
        if_modified_since=now - timedelta(minutes=5)  # Data from 5 minutes ago
    )
    print("Data has been modified since the specified time")
except ResourceNotModified:
    print("Data has not been modified since the specified time")
    # Use cached data instead
```

See [Scraping Documentation](./scraping.md) for more information on using the `If-Modified-Since` header.

## Combining Exception Handlers

You can combine exception handlers to handle different types of errors in different ways:

```python
from aiosteampy import SteamClient, App, AppContext, SteamError, LoginError, EResultError, SessionExpired, RateLimitExceeded

client = SteamClient(...)

try:
    await client.login()
    await client.get_inventory(AppContext.CS2)
    await client.place_buy_order("AK-47 | Redline (Field-Tested)", App.CS2, price=1000)
except LoginError as e:
    print(f"Login failed: {e}")
    # Handle login errors
except SessionExpired as e:
    print(f"Session expired: {e}")
    # Re-login and try again
except RateLimitExceeded as e:
    print(f"Rate limited: {e}")
    # Wait and try again with slower rate
except EResultError as e:
    print(f"Steam returned an error: {e}")
    # Handle specific error codes
except SteamError as e:
    print(f"Other Steam error: {e}")
    # Handle other Steam errors
except Exception as e:
    print(f"Non-Steam error: {e}")
    # Handle non-Steam errors
```

Remember to always check the method's docstring for information about which exceptions it may raise.
