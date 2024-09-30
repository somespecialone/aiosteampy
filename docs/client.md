!!! danger "Deprecated documentation"
    This and next parts of the documentation are not completed yet and contains information for old version.
    Be careful!


### Init & login

To prevent additional requests to `steam` when logging in we can pass all known data to init method.

[//]: # (TODO identity_secret is optinal now)
[//]: # (TODO write anywhere about App and AppContext)

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

!!! note "`Steam Web Api Key` registration"
    Obtaining `api key` will be automatically registered on
    `https://github.com/somespecialone/aiosteampy` domain during data initialization.
    It is highly recommended to register `api key` on _domain of your choice_.

??? info "`client.login` args and data fetching"
    You can bypass this if pass `init_data=False`. But keep in mind - methods which requires missed data will throw errors.

Addition to args above, there is:

* `lang` - language of requests data. Do not recommend to change this until you know what you're doing.
* `tz_offset` - string of time zone offset that will be set as cookie value.
* `session` - [aiohttp.ClientSession](https://docs.aiohttp.org/en/stable/client_advanced.html#client-session).

!!! warning "Session"
    If you create `session` by yourself - `raise_for_status` must be `True`,
    `ClientSession(..., raise_for_status=True)`. If not, errors will be not handled right and this will cause strange
    behavior.

### Public methods client

Have methods that doesn't require authentication.
[Docs here](public.md)

```python
from aiosteampy import SteamPublicClient

client = SteamPublicClient()

histogram = await client.get_item_orders_histogram(12345687)
...
```

### Proxies 🌐

Read more about proxy support on the [dedicated page](./proxies.md)

### Inheritance

In case you need to use multiple inheritance and `__slots__`, you can subclass `SteamCommunityMixin`:

```python
from aiosteampy.client import SteamClientBase, SteamClient


class MyClient(SteamClientBase, ...):
    __slots__ = (
        *SteamClient.__slots__,
        "attr",
        "attr1",  # your slots
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        ...
```

[//]: # (TODO inheritance, mixins)
