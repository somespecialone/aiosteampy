<!--header-start-->

# AIOSTEAMPY

[![Made in Ukraine](https://img.shields.io/badge/made_in-ukraine-ffd700.svg?labelColor=0057b7)](https://stand-with-ukraine.pp.ua)
[![steam](https://shields.io/badge/steam-1b2838?logo=steam)](https://store.steampowered.com/)
[![license](https://img.shields.io/github/license/somespecialone/aiosteampy)](https://github.com/somespecialone/aiosteampy/blob/master/LICENSE)
[![pypi](https://img.shields.io/pypi/v/aiosteampy)](https://pypi.org/project/aiosteampy)
[![versions](https://img.shields.io/pypi/pyversions/aiosteampy)](https://pypi.org/project/aiosteampy)
[![Tests](https://github.com/somespecialone/aiosteampy/actions/workflows/tests.yml/badge.svg)](https://github.com/somespecialone/aiosteampy/actions/workflows/tests.yml)
[![Publish](https://github.com/somespecialone/aiosteampy/actions/workflows/publish.yml/badge.svg)](https://github.com/somespecialone/aiosteampy/actions/workflows/publish.yml)
[![Docs](https://github.com/somespecialone/aiosteampy/actions/workflows/docs.yml/badge.svg)](https://github.com/somespecialone/aiosteampy/actions/workflows/docs.yml)
[![codecov](https://codecov.io/gh/somespecialone/aiosteampy/branch/master/graph/badge.svg?token=SP7EQKPIQ3)](https://codecov.io/gh/somespecialone/aiosteampy)
[![CodeFactor](https://www.codefactor.io/repository/github/somespecialone/aiosteampy/badge)](https://www.codefactor.io/repository/github/somespecialone/aiosteampy)
[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Previously this library was a soft fork of [bukson/steampy](https://github.com/bukson/steampy) and created only to
provide asynchronous methods and proxies support.
But now it _standalone_ project. Created by myself for steam trading purposes mostly.

---

[![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner-direct-single.svg)](https://stand-with-ukraine.pp.ua)

<!--header-end-->

> [!IMPORTANT]
> See full documentation [here](https://aiosteampy.somespecial.one/) 📖

<!--install-start-->

## Installation

```shell
pip install aiosteampy
```

```shell
pipenv install aiosteampy
```

```shell
poetry add aiosteampy
```

Project have some extras [currencies converter](https://aiosteampy.somespecial.one/ext/converter/),
[socks proxies](https://aiosteampy.somespecial.one/proxies).
To install them all, please, use `aiosteampy[all]` install target:

```shell
poetry add aiosteampy[all]
```

<!--install-end-->

> [!TIP]
> [aiohttp docs](https://docs.aiohttp.org/en/stable/#installing-all-speedups-in-one-command) recommends installing
> speedups (`aiodns`, `cchardet`, ...)

<!--intro-start-->

AIOSTEAMPY use [aiohttp](https://github.com/aio-libs/aiohttp) underneath to do asynchronous requests to steam servers,
with modern async/await syntax.

> Generally, project inspired most
> by [DoctorMcKay/node-steamcommunity](https://github.com/DoctorMcKay/node-steamcommunity)

## Key features

- Stateless: the main idea was a low-middle layer API wrapper of some steam services and methods like market,
  tradeoffers, confirmations, steamguard, etc. But if you want to cache your entities data (listings, confirmations,
  ...) [there is some methods to help](https://aiosteampy.somespecial.one/examples/states/).
- Declarative: there is models almost for every data.
- Typed: for editor support most things are typed.
- Short: I really tried to fit most important for steam trading methods.
- Connection behind web proxy.

## What can I do with this

- Operate with steam trade offers for any manner.
- Sell, buy items on market. Place, cancel orders.
- Login trough steam to 3rd party sites.
- Fetch data from market.
- Manipulate many accounts with proxies for each session.
- Store and load cookies to stay logged in.
- Convert market prices into different currencies.

## What I can't do

- Chat (at least for now).
- Get apps, packages.
- All, that need connection to CM.
- Interact with game servers (inspect CS2 (ex. CSGO) items, ...).
- Edit profile, social interaction(groups, clans).
- Handle entities (listings, items, tradeoffers) lifecycle for easy if you need to store it.

<!--intro-end-->

## Tests 🧪

Read [test documentation](https://aiosteampy.somespecial.one/tests/) 📖

<!--footer-start-->

## Contribution 💛

There is no rules or requirements to contribute. Feedbacks, suggests, other are welcome.
I will be very grateful for helping me get the things right.

## Credits

- [bukson/steampy](https://github.com/bukson/steampy)
- [aiohttp-socks](https://github.com/romis2012/aiohttp-socks)
- [croniter](https://github.com/kiorky/croniter)
- [DoctorMcKay/node-steamcommunity](https://github.com/DoctorMcKay/node-steamcommunity)
- [Identifying Steam items](https://dev.doctormckay.com/topic/332-identifying-steam-items/)
- [Revadike/InternalSteamWebAPI](https://github.com/Revadike/InternalSteamWebAPI)
- [Gobot1234/steam.py](https://github.com/Gobot1234/steam.py)
- [Steam Market id's storage repo](https://github.com/somespecialone/steam-item-name-ids)
- [steamapi.xpaw.me](https://steamapi.xpaw.me/)
- [Steam Exchange Rate Tracker](https://github.com/somespecialone/sert)

<!--footer-end-->
