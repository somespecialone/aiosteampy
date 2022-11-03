# <p align="center">Asyncsteampy</p>

[![license](https://img.shields.io/github/license/somespecialone/asyncsteampy)](https://github.com/somespecialone/asyncsteampy/blob/master/LICENSE)
[![pypi](https://img.shields.io/pypi/v/asyncsteampy)](https://pypi.org/project/asyncsteampy)
[![Tests](https://github.com/somespecialone/asyncsteampy/actions/workflows/tests.yml/badge.svg)](https://github.com/somespecialone/asyncsteampy/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/somespecialone/asyncsteampy/branch/master/graph/badge.svg?token=H3JL81SL7P)](https://codecov.io/gh/somespecialone/asyncsteampy)
[![CodeFactor](https://www.codefactor.io/repository/github/somespecialone/asyncsteampy/badge)](https://www.codefactor.io/repository/github/somespecialone/asyncsteampy)
[![versions](https://img.shields.io/pypi/pyversions/asyncsteampy)](https://pypi.org/project/asyncsteampy)
[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![steam](https://shields.io/badge/steam-1b2838?logo=steam)](https://store.steampowered.com/)

> ### This library is a soft fork of [bukson/steampy](https://github.com/bukson/steampy) ⚠ and created only to provide asynchronous methods and proxies support.
> #### Docs, examples you can read from original [README](https://github.com/bukson/steampy#readme). Differences of usage and new features listed below 📖
> #### Must work with python 3.6 and above like origin, but tested only on `3.10` ⚡
---

## Navigation

- [**Installation**](#installation)
- [**Login&Init**](#logininit)
- [**AsyncIO**](#asyncio)
- [**Proxy support**](#proxy-support)
- [**Tests**]()

---

## Installation

```shell
pip install asyncsteampy

pipenv install asyncsteampy

poetry add asyncsteampy
```

## Login&Init

Now you don't need to pass `username`, `password`, `steamguard` args to `login` method, you can do this in constructor.

```python
from asyncsteampy.client import SteamClient as AsyncSteamClient

async_steam_client = AsyncSteamClient('MY_USERNAME', 'MY_PASSWORD', 'PATH_TO_STEAMGUARD_FILE/STEAMGUARD_DICT',
                                      api_key="API_KEY")
```

Instead of passing `str` path or `pathlib.Path` to `steamguard.txt` file or even json serialized string you can just use
dict object:

```py
steamguard = {
    "steamid": "YOUR_STEAM_ID_64",
    "shared_secret": "YOUR_SHARED_SECRET",
    "identity_secret": "YOUR_IDENTITY_SECRET",
}
```

## AsyncIO

All methods that require connection to steam network now have asyncio support (it
uses [aiohttp](https://github.com/aio-libs/aiohttp)) and are asynchronous : `client`, `market`, `chat`.

```py
from asyncsteampy.client import SteamClient as AsyncSteamClient

async_steam_client = AsyncSteamClient('MY_USERNAME', 'MY_PASSWORD', 'PATH_TO_STEAMGUARD_FILE/STEAMGUARD_DICT',
                                      api_key="API_KEY")
await async_steam_client.login()
buy_order_id = "some_buy_order_id"
response = await async_steam_client.market.cancel_buy_order(buy_order_id)
# do other async work
await async_steam_client.close(logout=True)
```

If you end your operations, ⚠️ `keep in mind`, you always need to close your `async_steam_client`. This will
do `logout` (if `logout=True`)
and close `aiohttp` [session](https://docs.aiohttp.org/en/stable/client_reference.html#client-session) properly. Also,
you can `await async_steam_client.logout()` without closing session if you need this for some reason.

Async context manager usage example:

```py
from asyncsteampy.client import SteamClient as AsyncSteamClient

async with AsyncSteamClient('MY_USERNAME', 'MY_PASSWORD', 'PATH_TO_STEAMGUARD_FILE/STEAMGUARD_DICT',
                            api_key="API_KEY") as async_steam_client:
    await async_steam_client.do_what_you_need()
```

There you don't need to call `close`, async context manager do it automatically when execution passes the block of code.

## Proxy support

If your proxy type is socks4/5 you should look at this small but precious
library [aiohttp-socks](https://github.com/romis2012/aiohttp-socks), if proxy type http/https, or you don't
like `aiohttp-socks` you can use [aiohttp-proxy](
https://github.com/Skactor/aiohttp-proxy) instead.

```python
import aiohttp
from aiohttp_socks import ProxyConnector

from asyncsteampy.client import SteamClient as AsyncSteamClient

connector = ProxyConnector.from_url('proxy_type://proxy_url_with_or_no_auth')
session_with_proxy = aiohttp.ClientSession(connector=connector)

# Finally, pass session object in AsyncSteamClient

async_steam_client = AsyncSteamClient(..., session=session_with_proxy)
async with AsyncSteamClient(..., session=session_with_proxy) as async_steam_client:
    ...
```

## Tests

To run tests clone repo, install with dev dependencies

```shell
poetry install
```

Create env variables listed in [tests/data](tests/data.py) and run `pytest` from project dir:

```shell
pytest
```
