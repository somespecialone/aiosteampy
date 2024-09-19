What type of exceptions can be raised in method you can see at corresponding `docstring`.

All `Steam` side errors does have `SteamError` class.

So, to catch all errors of this type, all you need to do next is:

```python
from aiosteampy import SteamError

try:
    await client.login()
except SteamError as e:
    print("Catch Steam error", e)
```

But, more detailed, there is an exception hierarchy - next errors subclass `SteamError`:

- **EResultError** - raised when `Steam` response with error code (`success` field in json response). Look at
[steamerrors.com](https://steamerrors.com)
- **LoginError** - when there is an error in login process occurred
- **SessionExpired** - means that your session is expired, and you need to do login again.
Raise decision based solely on response from `Steam` and no internal logic, for ex. check `access_token`
- **RateLimitExceeded** - you have been rate limited
- **ResourceNotModified** - means that requested data has not been modified since timestamp
from passed `If-Modified-Since` header value

[More information](./scraping.md) regarded last two exceptions

Respecting the hierarchy:

```python
from aiosteampy import SteamError, LoginError, EResultError

try:
    await client.login()
except LoginError as e:
    print("Catch specific login error", e)
except EResultError as e:
    print("Catch e result error", e)
except SteamError as e:
    print("Catch other Steam errors (there is nothing in login method, btw)", e)
```
