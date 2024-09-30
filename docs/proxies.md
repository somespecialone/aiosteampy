# Web proxies

It is possible to hide all interactions with `Steam` servers (including all `session` requests) behind a web proxy.

!!! warning "HTTPS proxies"
    [Aiohttp](https://docs.aiohttp.org/en/stable/) has no support for `HTTPS` proxies at the current moment.
    You can read more [here](https://docs.aiohttp.org/en/stable/client_advanced.html#proxy-support)

## First and last steps

To get `SteamClient` to connect, log in, and make requests to `Steam` through a web proxy,
you can pass web proxy url as `string` when creating an instance:

```python
from aiosteampy import SteamClient

client = SteamClient(..., proxy="http://my-proxy.com")
```

### Session and proxy

!!! danger "Bind your session to a proxy"
    `session` and `proxy` arguments are mutually exclusive. If you want to pass a `session` created by yourself,
    you are responsible for binding `session` to `proxy`

If you want to use web proxy for client and pass own session,
you need to make requests of `aiohttp.ClientSession` go through it by yourself. 

In `utils` module there is a function for `http\s` type of proxy: `patch_session_with_http_proxy`

```python
from aiohttp import ClientSession

from aiosteampy import SteamClient
from aiosteampy.utils import patch_session_with_http_proxy

patched_session = patch_session_with_http_proxy(
    ClientSession(raise_for_status=True),
    "http://my-proxy.com",
)

client = SteamClient(..., session=patched_session)
```

For `socks` type of web proxy [read next](#own-session)

## Authorization

To pass username, password of the web proxy use `url string` with next format:

`schema://user:password@host:port`

For example:

```python
from aiosteampy import SteamClient

proxy_url_with_auth = "http://username:password@my-proxy.com"
# or
proxy_url_with_auth = "http://username:password@127.0.0.1:1080"

client = SteamClient(..., proxy=proxy_url_with_auth)
```

## SOCKS

!!! note "Extra dependency"
    To use `socks` type of the proxies project needs
    [aiohttp-socks](https://github.com/romis2012/aiohttp-socks) package.

`Aiosteampy` does all the necessary work behind the curtain, all you need to do is install `aiosteampy[socks]` dependency
target.

```shell
poetry add aiosteampy[socks]
```

Then pass web proxy url:

```python
from aiosteampy import SteamClient

client = SteamClient(..., proxy="socks5://username:password@127.0.0.1:1080")
```

!!! info "Supported `socks` types"
    All supported proxy types you can find in [aiohttp-socks repository page](https://github.com/romis2012/aiohttp-socks)

### Own session

In such case `aiosteampy` can do nothing behind the curtain 😁

Use `aiohttp_socks.ProxyConnector` as `connector`:

```python
from aiohttp import ClientSession
from aiohttp_socks import ProxyConnector

from aiosteampy import SteamClient

session = ClientSession(
    raise_for_status=True,
    connector=ProxyConnector.from_url("socks5://my-proxy.com"),
)

client = SteamClient(..., session=session)
```
