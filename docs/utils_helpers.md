# Utility and Helper Functions

This document describes the utility and helper functions available in the `aiosteampy` library.

## Utils

[Utils.py](https://github.com/somespecialone/aiosteampy/blob/master/aiosteampy/utils.py) in a repository

### Authentication and Security

- `gen_two_factor_code(shared_secret, timestamp=None)`: Generates a Steam two-factor authentication code using the provided shared secret.
- `generate_confirmation_key(identity_secret, tag, timestamp=None)`: Generates a confirmation key for Steam mobile confirmations.
- `generate_device_id(steam_id)`: Generates a device ID based on the Steam ID.
- `extract_openid_payload(page_text)`: Extracts OpenID payload from a page's HTML content.
- `do_session_steam_auth(session, auth_url)`: Performs Steam authentication for a session.
- `decode_jwt(token)`: Decodes a JWT token.

### Session and Cookie Management

- `get_cookie_value_from_session(session, url, field)`: Retrieves a specific cookie value from a session.
- `remove_cookie_from_session(session, url, field)`: Removes a specific cookie from a session.
- `update_session_cookies(session, cookies)`: Updates session cookies with provided cookies.
- `get_jsonable_cookies(session)`: Gets cookies from a session in a JSON-serializable format.
- `add_cookie_to_session(session, url, name, value, ...)`: Adds a cookie to a session with specified parameters.
- `generate_session_id()`: Generates a random session ID.
- `patch_session_with_http_proxy(session, proxy)`: Configures a session to use an HTTP proxy.

### Steam ID Utilities

- `steam_id_to_account_id(steam_id)`: Converts a Steam ID to an account ID.
- `account_id_to_steam_id(account_id)`: Converts an account ID to a Steam ID.
- `generate_device_id(steam_id)`: Generates a device ID from a Steam ID.

### Market and Trading Utilities

- `create_ident_code(*args, sep=":")`: Creates an identification code for Steam items.
- `receive_to_buyer_pays(amount, ...)`: Calculates the amount a buyer pays based on what the seller receives.
- `buyer_pays_to_receive(amount, ...)`: Calculates the amount a seller receives based on what the buyer pays.
- `calc_market_listing_fee(price, ...)`: Calculates the fee for a market listing.
- `find_item_nameid_in_text(text)`: Finds an item's name ID in text.
- `make_inspect_url(...)`: Creates a URL for inspecting an item.

### Time Utilities

- `parse_time(value)`: Parses a time string into a datetime object.
- `format_time(d)`: Formats a datetime object into a string.

### Decorators and Function Utilities

- `async_throttle(seconds, ...)`: Decorator to throttle async function calls.
- `attribute_required(attr, msg=None)`: Decorator to check if an instance has a required attribute.
- `to_int_boolean(s)`: Converts a value to an integer boolean (0 or 1).

## Helpers

[Heplers.py](https://github.com/somespecialone/aiosteampy/blob/master/aiosteampy/helpers.py) in a repository


### Session Management

- `restore_from_cookies(cookies, client)`: Restores a client session from cookies. Returns `True` if cookies are valid and not expired.

### Decorators

- `currency_required`: Decorator that checks if the currency attribute is set before executing a method.
- `identity_secret_required`: Decorator that checks if the _identity_secret attribute is set before executing a method.
