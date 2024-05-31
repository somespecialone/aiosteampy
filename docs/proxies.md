# Web proxies

It is possible to hide all interactions with `Steam` servers (including all `session` requests) behind a web proxy.

!!! warning "HTTPS proxies"
    [Aiohttp](https://docs.aiohttp.org/en/stable/) has no support for `HTTPS` proxies at the current moment.
    You can read more [here](https://docs.aiohttp.org/en/stable/client_advanced.html#proxy-support)

## First and last steps

To get `SteamClient` to connect, log in, and make requests to `Steam` through a web proxy,
you can pass `web proxy url string` when creating an instance:

```python
from aiosteampy import SteamClient

client = SteamClient(..., proxy="http://my-proxy.com")
```

## Authorization

To pass username, password of the web proxy use `url string` with next format:

`schema://user:password@host:port`

For example:

```python
proxy_url_with_auth = "http://username:password@my-proxy.com"
# or
proxy_url_with_auth = "http://username:password@127.0.0.1:1080"

client = SteamClient(..., proxy=proxy_url_with_auth)
```

## SOCKS proxy type

!!! note "Extra dependency"
    To use `socks` type of the proxies you need [aiohttp_socks](https://github.com/romis2012/aiohttp-socks) package.

`Aiosteampy` does all the necessary work behind the curtain, all you need to do is install `aiosteampy[socks]` dependency
target.

```shell
poetry add aiosteampy[socks]
```

Then pass web proxy url:

```python
client = SteamClient(..., proxy="socks5://username:password@127.0.0.1:1080")
```

!!! tip "Supported `socks` types"
    All supported proxy types you can find in [aiohttp_socks repository page](https://github.com/romis2012/aiohttp-socks)
