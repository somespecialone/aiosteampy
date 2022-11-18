### Init & login

To prevent additional requests to `steam` when logging in we can pass all known data to init method.

```python
from aiosteampy import SteamClient, Currency


client = SteamClient(
    "username",
    "password",
    112233,  # steam id(64) or account id(32)
    shared_secret="shared secret",
    identity_secret="identity secret",
    api_key="api key",
    trade_token="trade token",
    wallet_currency=Currency.UAH,
    wallet_country="UA",
)

await client.login()
```

??? note "`client.login` args and data fetching"
    You can prevent this if pass `init_data=False`. But keep in mind, that methods required missed data will throw errors.

Addition to args above, there is:

* `steam_fee` - fee of steam. Don't know may it change or not, but for flexibility it exists.
  If you pass `None` - data will be fetched.
* `publisher_fee` - same as `steam_fee`, fetched in single request.
* `lang` - language of requests data. Do not recommend to change this until you know what you're doing.
* `tz_offset` - just time zone offset that will be set to cookie.
* `session` - [aiohttp.ClientSession](https://docs.aiohttp.org/en/stable/client_advanced.html#client-session).
  

!!! warning "Session"
    If you create `session` by yourself - `raise_for_status` must be `True`,
    `ClientSession(..., raise_for_status=True)`. If not, errors will be not handled right and this will cause strange
    behavior.

### Proxies

For proxies support you can use [aiohttp-socks](https://github.com/romis2012/aiohttp-socks) as you can create `session` by
yourself.


### Inheritance

In case you need to use multiple inheritance and `__slots__`, you may subclass `SteamCommunityMixin`:

```python
from aiosteampy.client import SteamCommunityMixin, SteamClient


class MyClient(SteamCommunityMixin, ...):
    __slots__ = (
        *SteamClient.__slots__,
        "attr",
        "attr1",  # your slots
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        ...
```