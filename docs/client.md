# Client Classes

The aiosteampy library provides several client classes for interacting with the Steam API. 
Each client class has specific responsibilities and capabilities.

## Client Classes and Their Responsibilities

### SteamPublicClient

The `SteamPublicClient` class provides methods that don't require authentication. 
It's useful for accessing public Steam data like market listings, user inventories, and price information.

```python
from aiosteampy import SteamPublicClient, App

client = SteamPublicClient()

# Get market listings for an item
listings, total_count, last_modified = await client.get_item_listings("AK-47 | Redline (Field-Tested)", App.CS2)

# Get item orders histogram
item_name_id = await client.get_item_name_id("Revolution Case", App.CS2)
histogram, last_modified = await client.get_item_orders_histogram(item_name_id)
```

See the [Public API Methods](./public.md) page for more details on available methods.

### SteamClient

The `SteamClient` class is the main client for authenticated interactions with Steam. 
It inherits from `SteamPublicClient` and includes **all the functionality from mixins listed below**.

```python
from aiosteampy import SteamClient, Currency, AppContext

client = SteamClient(
    steam_id=76561198012345678,  # steam id(64) or account id(32)
    username="your_username",
    password="your_password",
    shared_secret="your_shared_secret",
    identity_secret="your_identity_secret",  # optional, required for confirmations
    api_key="your_api_key",  # optional
    trade_token="your_trade_token",  # optional
    wallet_currency=Currency.UAH,  # optional
    wallet_country="UA",  # optional
)

# Login to Steam
await client.login()

# Prepare the client (get trade token, API key, etc.)
await client.prepare(api_key_domain="your-domain.com")

# Access your inventory
inventory, total_count, last_asset_id = await client.get_inventory(AppContext.CS2)

# Place a market listing
item = await client.get_inventory_item(AppContext.CS2, asset_id=1234567890)
listing_id = await client.place_sell_listing(item, price=10000)  # price in cents
```

## Initialization and Login

To prevent additional requests to Steam when logging in, you can pass all known data to the init method:

```python
from aiosteampy import SteamClient, Currency, Language

client = SteamClient(
    steam_id=76561198012345678,  # steam id(64) or account id(32)
    username="your_username",
    password="your_password",
    shared_secret="your_shared_secret",
    identity_secret="your_identity_secret",  # optional, required for confirmations
    api_key="your_api_key",  # optional
    trade_token="your_trade_token",  # optional
    wallet_currency=Currency.UAH,  # optional
    wallet_country="UA",  # optional
    language=Language.ENGLISH,  # optional
    tz_offset="0,0",  # optional
)

await client.login()
```

!!! note "API Key Not Required"
    Since the end of March 2024, an API key is not required to access the Steam Web API. Users can freely use the 
    full functionality of the library without an API key.

### Preparing the Client

The `prepare()` method prepares the client by loading main attributes (trade token, currency, country) from Steam. 
It also ensures privacy settings are set correctly for inventory and related features.

```python
# Prepare the client (get trade token, set privacy settings, etc.)
await client.prepare()

# If you want to register an API key (optional)
await client.prepare(api_key_domain="your-domain.com")
```

When using the `prepare()` method with an `api_key_domain` parameter, an API key will be automatically registered 
for that domain if one doesn't exist. It is highly recommended to register the API key on a domain that you control.

### Additional Parameters

The client initialization accepts several additional parameters:

* `language` - Language for Steam responses (default: `Language.ENGLISH`)
* `tz_offset` - Timezone offset string that will be set as a cookie value (default: `"10800,0"`)
* `session` - Custom [aiohttp.ClientSession](https://docs.aiohttp.org/en/stable/client_advanced.html#client-session)
* `proxy` - Proxy URL as a string (e.g., `"http://username:password@host:port"`)
* `user_agent` - Custom User-Agent header value

!!! warning "Session Configuration"
    If you create a custom session, `raise_for_status` must be set to `True`: 
    `ClientSession(..., raise_for_status=True)`. Otherwise, errors will not be handled correctly, which can cause 
    unexpected behavior.

## Mixins and Their Functionality

The client classes use several mixins to provide different functionality:

### SteamHTTPTransportMixin

Base mixin that provides HTTP transport functionality, including session management and request handling.

Methods and properties:

- `user_agent`: Get/set the User-Agent header for requests
- `language`: Get/set the language for Steam responses
- `tz_offset`: Get/set the timezone offset cookie
- `session_id`: Get/set the sessionid cookie for Steam Community
- `get_session_id`/`set_session_id`: Get/set the sessionid cookie for a specific Steam domain
- `proxy`: Get the current proxy configuration

### SteamCommunityPublicMixin

Provides methods for accessing public Steam Community data, such as user inventories, market listings, and price 
information.

Take a look at public methods on the [dedicated page](./public.md)

### SteamGuardMixin

Handles Steam Guard functionality, including generating two-factor authentication codes.

Methods and properties:

- `account_id`: Get the 32-bit account ID from the 64-bit Steam ID
- `two_factor_code`: Generate a two-factor authentication code using the shared secret

### LoginMixin

Manages the login process, including handling cookies, tokens, and session data.

Methods and properties:

- `login`: Authenticate with Steam using credentials and Steam Guard
- `logout`: End the current session
- `access_token`/`refresh_token`: Get/set the access and refresh tokens
- `is_access_token_expired`/`is_refresh_token_expired`: Check if tokens are expired
- `refresh_access_token`: Refresh the access token when it expires
- `is_session_alive`: Check if the current session is still valid

### ProfileMixin

Provides methods for managing user profiles, including getting and setting profile data, privacy settings, and trade URLs.

Methods and properties:

- `trade_url`/`profile_url`: Get the trade URL and profile URL
- `get_profile_data`: Retrieve profile information
- `edit_profile`: Update profile information (name, summary, location, etc.)
- `edit_privacy_settings`: Update privacy settings for various profile elements
- `register_new_trade_url`: Generate a new trade URL
- `get_trade_token`: Retrieve the trade token from the profile
- `upload_avatar`: Upload a new profile avatar

### MarketMixin 💹

Handles Steam Market functionality, including placing buy/sell orders, managing listings, and retrieving market history.

Take a look at market methods on the [dedicated page](./market.md)

### TradeMixin

Manages trade offers, including creating, accepting, declining, and retrieving trade offers.

Take a look at trade-offers related methods on the [dedicated page](./trade.md)

### ConfirmationMixin

Handles mobile confirmations for market listings and trade offers.

Methods:

- `get_confirmations`: Retrieve all pending confirmations
- `confirm_sell_listing`: Confirm a market listing
- `confirm_trade_offer`: Confirm a trade offer
- `confirm_api_key_request`: Confirm an API key request
- `allow_all_confirmations`: Allow all pending confirmations
- `allow_confirmation`/`allow_multiple_confirmations`: Allow specific confirmation(s)
- `get_confirmation_details`: Get detailed information about a confirmation

## Proxies 🌐

Read more about proxy support on the [dedicated page](./proxies.md)

## Custom Client Implementation

If you need to create a custom client with specific functionality, you can subclass `SteamClientBase` or 
`SteamPublicClientBase`:

```python
from aiosteampy.client import SteamClientBase

class MyCustomClient(SteamClientBase):
    __slots__ = (
        *SteamClientBase.SLOTS,
        "custom_attribute",  # your custom attributes
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_attribute = "custom value"

    async def custom_method(self):
        # Your custom implementation
        pass
```

If you need to use multiple inheritance with `__slots__`, make sure to include all the necessary slots:

```python
from aiosteampy.client import SteamClientBase, SteamClient

from some_other_library import SomeOtherClass

class MyClient(SteamClientBase, SomeOtherClass):
    __slots__ = (
        *SteamClientBase.SLOTS,
        *SomeOtherClass.__slots__,
        "custom_attribute",  # your custom attributes
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Your custom initialization
```
