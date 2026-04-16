<!--header-start-->

# AIOSTEAMPY

[![Made in Ukraine](https://img.shields.io/badge/made_in-ukraine-ffd700.svg?labelColor=0057b7)](https://stand-with-ukraine.pp.ua)
[![steam](https://shields.io/badge/steam-1b2838?logo=steam)](https://store.steampowered.com/)
[![license](https://img.shields.io/github/license/somespecialone/aiosteampy)](https://github.com/somespecialone/aiosteampy/blob/main/LICENSE)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Snyk Badge](https://img.shields.io/badge/Snyk-4C4A73?logo=snyk&logoColor=fff&style=flat)](https://security.snyk.io/package/pip/aiosteampy)
[![pypi](https://img.shields.io/pypi/v/aiosteampy)](https://pypi.org/project/aiosteampy)
[![Release](https://github.com/somespecialone/aiosteampy/actions/workflows/release.yml/badge.svg)](https://github.com/somespecialone/aiosteampy/actions/workflows/release.yml)
[![Docs](https://github.com/somespecialone/aiosteampy/actions/workflows/docs.yml/badge.svg)](https://github.com/somespecialone/aiosteampy/actions/workflows/docs.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/somespecialone/aiosteampy)

Manage Steam sessions, Guard, Market, trade offers and more.

---

[![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner-direct-single.svg)](https://stand-with-ukraine.pp.ua)

<!--header-end-->

> [!IMPORTANT]
> The project is heading toward `1.0.0` and there can be some changes until stable release
> but library design as a whole with most API will stay.

## Documentation

- 📖 Project documentation is available at [aiosteampy.somespecial.one](https://aiosteampy.somespecial.one).
- 🧠 Generated [DeepWiki](https://deepwiki.com/somespecialone/aiosteampy).

<!--install-start-->

## Installation

Project published on [PyPI](https://pypi.org/) under [aiosteampy](https://pypi.org/project/aiosteampy/) name
so can be installed with:

```sh
pip install aiosteampy
poetry add aiosteampy
uv add aiosteampy
```

### Prereleases

To install _prerelease_ versions (alpha, beta, release candidates),
consider allowing the package manager to do it:

```sh
pip install --pre aiosteampy
poetry add --allow-prereleases aiosteampy
uv add --prerelease aiosteampy
```

### Extras

Extras can be installed with `aiosteampy[<extra>]` install target.

Project uses [aiohttp](https://github.com/aio-libs/aiohttp) as default _HTTP transport_ with all its
capabilities and limitations.

- `socks` - enable **socks** type web proxy support for **default** _HTTP transport_.
- `wreq` - [wreq-python](https://github.com/0x676e67/wreq-python) _HTTP transport_ implementation.
  Supports *proxies, HTTP/2, and browser impersonification*. Will be **used automatically** once installed.

<!--install-end-->
<!--usage-start-->

## Quick start

Package separated into *main modules* which can be imported from ``aiosteampy`` namespace:

- `session` - `Steam Session` management and auth tokens negotiation.
- `guard` - `Steam Guard/Mobile Authenticator` (2FA) functionality.
- `client` - abstract container for `Steam` domains implementations (`Market`, `Trade Offers`, etc.).

### Session

`SteamSession` provides functionality to log into user account using either _credentials_
or _QR_. When the login process has been _finalized_ web auth cookies can be obtained
to enable interaction with `SteamCommunity` domains like `Confirmations` (see [guard](#guard)),
`Market`, `TradeOffers`, `Profile` and `Inventory` (see [client](#client)).
Methods `serialize` and `deserialize` allows to _dump/load_ `SteamSession` into/from _JSON-safe_ dict.

Demonstrative example of using `SteamSession` to log into account
with credentials, obtaining _web cookies_ and finally _dump_ session into file:

```python
import asyncio
import json

from aiosteampy.session import SteamSession, GuardConfirmationRequired


async def login_with_credentials():
    session = SteamSession()

    account_name = input("Input login: ")
    password = input("Input password: ")

    try:
        await session.with_credentials(account_name, password)
    except GuardConfirmationRequired as e:
        if e.email_code:
            code = input("Code from Steam has been sent to your email. Paste it here: ")
            await session.submit_auth_code(code, "email")
        elif e.device_code:
            code = input("Input code from Mobile Device Authenticator: ")
            await session.submit_auth_code(code, "device")
        else:
            input(
                ("Steam requests device or email confirmation. "
                 "Click on the link from email or mobile application and press enter.")
            )

    await session.finalize()

    print("Access token: ", session.access_token)
    print("Refresh token: ", session.refresh_token)

    await session.obtain_cookies()

    print("Web cookies obtained!")

    await session.transport.close()

    session_dump = session.serialize()

    with open(f"./{account_name}.session.json", "w") as f:
        json.dump(session_dump, f, indent=2)


asyncio.run(login_with_credentials())
```

Session can then be _loaded_ from a dump.
Although not verified for expiration, tokens and cookies will be restored:

```python
with open(f"./{account_name}.session.json", "r") as f:
    session = SteamSession.deserialize(json.load(f))
```

### Guard

`SteamGuard` embodies `Steam Mobile Authenticator` functionality from mobile app.
Can activate account _2FA_ (similar to using [SDA](https://github.com/Jessecar96/SteamDesktopAuthenticator)),
generate _auth codes_, sign _auth requests_ made with other `SteamSession` by QR, handle `Steam Confirmations`.
Eventually, guard requires session with `mobile` app platform.

Here we're using `SteamGuard` to activate `Authenticator` and dump `SteamGuardAccount` data into a file then:

```python
import json
import asyncio

from aiosteampy.session import SteamSession, Platform
from aiosteampy.guard import SteamGuard, SmsConfirmationRequired, EmailConfirmationRequired


async def enable_two_fa():
    session = SteamSession(..., platform=Platform.MOBILE)

    guard = SteamGuard(session)

    try:
        guard.enable()
    except SmsConfirmationRequired as e:
        code = input(f"Guard activation code has been sent to your phone ({e.phone_hint}). Paste it here: ")
    except EmailConfirmationRequired:
        code = input("Guard activation code has been sent to your email. Paste it here: ")

    await guard.finalize(code)

    # Exported guard account contains secrets that cannot be retrieved once more
    # therefore, data must be saved ASAP to prevent loss of access to a user's Steam account
    guard_account = guard.export_account()
    with open(f"./{session.account_name or session.steam_id}.guard.json", "w") as f:
        json.dump(guard_account.serialize(), f)

    await guard.transport.close()


asyncio.run(enable_two_fa())
```

### Client

`SteamClient` composes all `Steam` domains implementations:
`Market`, `Trade Offers`, `Inventory`, `Profile`, `Wallet` and more. Each domain is 
responsible for related functionality. For example, `Market` domain contain methods
allow to retrieve and buy listings from `Steam Market`, place buy and sell orders.
`Trade Offers` provides methods to send, accept or deny offers and so on.

There is also a `SteamPublicClient` entity in `aiosteampy.client` namespace that allows interaction
with `Steam` from unauthenticated (anonymous) user perspective.

Using `SteamClient` with authenticated `SteamSession` to get _current user inventory items_:

```python
import asyncio

from aiosteampy.session import SteamSession
from aiosteampy.client import SteamClient, AppContext, App


async def get_inventory():
    session = SteamSession(...)

    client = SteamClient(session)

    # use predefined apps and their contexts
    cs2_default_inv = await client.inventory.get(AppContext.CS2)
    print("CS2 items: ", cs2_default_inv.items)

    cs2_trade_protected_inv = await client.inventory.get(AppContext.CS2_PROTECTED)
    print("CS2 trade protected items: ", cs2_trade_protected_inv.items)

    # create new App and AppContext
    BongoCatApp = App(3419430, "Bongo Cat")
    BongoCatDefault = BongoCatApp.with_context(2)

    bongo_cat_inv = await client.inventory.get(BongoCatDefault)
    print("Bongo Cat items: ", bongo_cat_inv.items)

    await client.transport.close()


asyncio.run(get_inventory())
```

Retrieving _item orders histogram_ from `SteamMarket` with an unauthenticated client:

```python
import asyncio

from aiosteampy.client import SteamPublicClient, App


async def get_histogram():
    client = SteamPublicClient()

    # Glock-18 | Fully Tuned (Field-Tested)
    histogram = await client.market.get_orders_histogram(176611887)

    print("Get histogram: ", histogram)

    await client.transport.close()


asyncio.run(get_histogram())
```

<!--usage-end-->
<!--intro-start-->

## Key features ✨

- **Stateful**: Manages user sessions state throughout the lifecycle.
- **Declarative**: There are models for ~~almost~~ every data.
- **Typed**: High-end support with extensive typing.
- **Friendly**: Intuitive and straightforward API.
- **Flexible**: Custom _HTTP transport_ layer can be implemented to fit user needs.
- **Asynchronous**: Fully async implementation using `asyncio`.

### What I can do with this

- Login using _credentials_ and _QR_, obtain auth web cookies.
- Operate `Trade Offers`: send, accept, decline, and counter.
- Place and cancel _buy/sell_ orders, purchase listings directly on `Steam Market`.
- _Dump & Load_ tokens and cookies to enable `Session` persistence.
- _De/serialize_ `Client` state reducing boilerplate.
- Retrieve, accept, and deny `Steam Mobile Device` confirmations.
- Enable `Steam Mobile Authenticator` for user account and save secrets.
- Import secrets from famous `SDA` format (`maFile`).
- Setup, edit information of user `Steam` profile.
- Get user account wallet balance, redeem `Wallet` or `Gift` codes.
- _Inspect_ CS2 items.
- Lost access to a user account by denying guidelines and warnings
  while being unvigilant.
- And more!

### What I can't do

- Buy app and their package on `Steam Store`.
- `WebSocket` connection to `Steam` servers.
- Interact with game servers (like find game match).
- Social interaction like groups, clans, and chat.
- Get confused with the complexity of usage.

<!--intro-end-->
<!--footer-start-->

## Contribution 💛

> Feedback, suggestions, and bug reports are welcome!

If you have any question regarding a project, don't hesitate to ask one in 
[Q&A](https://github.com/somespecialone/aiosteampy/discussions/categories/q-a).

Before creating a pull request, please try to **keep project style and code quality**
while contributing. Use formatter (currently [Ruff](https://github.com/astral-sh/ruff))
whenever possible respecting configuration in `pyproject.toml`.
Remove unrelated code changes from PR and generally be concise, thanks!.

## Credits

Sources of inspiration and ideas, concepts, and general knowledge:

- [DoctorMcKay/node-steam-session](https://github.com/DoctorMcKay/node-steam-session)
- [DoctorMcKay/node-steamcommunity](https://github.com/DoctorMcKay/node-steamcommunity)
- [dyc3/steamguard-cli](https://github.com/dyc3/steamguard-cli)
- [SteamRE/SteamKit](https://github.com/SteamRE/SteamKit)
- [DoctorMcKay/node-steamstore](https://github.com/DoctorMcKay/node-steamstore)
- [DoctorMcKay/node-steam-totp](https://github.com/DoctorMcKay/node-steam-totp)
- [SteamTracking/Protobufs](https://github.com/SteamTracking/Protobufs)
- [Gobot1234/steam.py](https://github.com/Gobot1234/steam.py)
- [steamapi.xpaw.me](https://steamapi.xpaw.me/)
- [bukson/steampy](https://github.com/bukson/steampy)

### Helpful links

- [Steam Market id's storage repo](https://github.com/somespecialone/steam-item-name-ids)
- [Jessecar96/SteamDesktopAuthenticator](https://github.com/Jessecar96/SteamDesktopAuthenticator)
- [achiez/NebulaAuth-Steam-Desktop-Authenticator](https://github.com/achiez/NebulaAuth-Steam-Desktop-Authenticator-by-Achies/)
- [Identifying Steam items](https://dev.doctormckay.com/topic/332-identifying-steam-items/)
- [CS2 Items Schema](https://github.com/somespecialone/cs2-items-schema)

<!--footer-end-->
