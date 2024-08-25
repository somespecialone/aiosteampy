<!--header-start-->

# AIOSTEAMPY

[![Made in Ukraine](https://img.shields.io/badge/made_in-ukraine-ffd700.svg?labelColor=0057b7)](https://stand-with-ukraine.pp.ua)
[![steam](https://shields.io/badge/steam-1b2838?logo=steam)](https://store.steampowered.com/)
[![license](https://img.shields.io/github/license/somespecialone/aiosteampy)](https://github.com/somespecialone/aiosteampy/blob/master/LICENSE)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Snyk Badge](https://img.shields.io/badge/Snyk-4C4A73?logo=snyk&logoColor=fff&style=flat)](https://security.snyk.io/package/pip/aiosteampy)
[![pypi](https://img.shields.io/pypi/v/aiosteampy)](https://pypi.org/project/aiosteampy)
[![versions](https://img.shields.io/pypi/pyversions/aiosteampy)](https://pypi.org/project/aiosteampy)
[![Tests](https://github.com/somespecialone/aiosteampy/actions/workflows/tests.yml/badge.svg)](https://github.com/somespecialone/aiosteampy/actions/workflows/tests.yml)
[![Publish](https://github.com/somespecialone/aiosteampy/actions/workflows/publish.yml/badge.svg)](https://github.com/somespecialone/aiosteampy/actions/workflows/publish.yml)
[![Docs](https://github.com/somespecialone/aiosteampy/actions/workflows/docs.yml/badge.svg)](https://github.com/somespecialone/aiosteampy/actions/workflows/docs.yml)
[![codecov](https://codecov.io/gh/somespecialone/aiosteampy/branch/master/graph/badge.svg?token=SP7EQKPIQ3)](https://codecov.io/gh/somespecialone/aiosteampy)
[![CodeFactor](https://www.codefactor.io/repository/github/somespecialone/aiosteampy/badge)](https://www.codefactor.io/repository/github/somespecialone/aiosteampy)
[![health](https://snyk.io//advisor/python/aiosteampy/badge.svg)](https://snyk.io//advisor/python/aiosteampy)

Previously this library was a soft fork of [bukson/steampy](https://github.com/bukson/steampy) with intend to
provide asynchronous methods and proxies support.
But now it _standalone_ project. 

> Created for steam trading purposes mostly.
Inspired by [DoctorMcKay/node-steamcommunity](https://github.com/DoctorMcKay/node-steamcommunity)

---

[![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner-direct-single.svg)](https://stand-with-ukraine.pp.ua)

<!--header-end-->

> [!IMPORTANT]
> The project is unstable and there might be some breaking changes in the future unless stable (**first major**) version 
> is released.
> 
> Take a look at [TODO](#todo-)
> 
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

## Key features ✨

- **Stateless**: low-middle layer API wrapper of some steam services and methods like market,
  tradeoffers, confirmations, steamguard, etc.
- **Declarative**: there is models or `TypedDict`s for every data.
- **Typed**: High-end support with extensive typing, tested on `VSCode` and `PyCharm`.
- **Simple**: Fit most important related to steam trading process methods.
- **Web proxy** support.

## What can I do with this

- Operate with steam trade offers.
- Sell, buy items on market. Place, cancel orders.
- Login trough steam to 3rd party sites.
- Fetch data from market.
- Manipulate many accounts with proxies for each session.
- Get and load cookies to stay logged in (session persistence).
- Convert market prices into different currencies.

## What I can't do

- Chat.
- Get apps, packages.
- All, that need connection to CM.
- Interact with game servers (inspect CS2 (ex. CSGO) items, ...).
- Social interaction(groups, clans).
- Handle entities (listings, items, tradeoffers) lifecycle for easy if you need to store it.

<!--intro-end-->

## Tests 🧪

> [!WARNING]
> Test cases and test code as a whole are deprecated and will not work until they are updated (a lot of work).
> I'll leave the code and this heading here as a reminder 🫣

[//]: # (Read [test documentation]&#40;https://aiosteampy.somespecial.one/tests/&#41; 📖)

<!--footer-start-->

## TODO 📃

> Hard to say **roadmap**. Can be a little changed or updated later, get ready.

Path to first **stable release**. Non-exhaustive list, scheduled tasks can be done earlier than the version mentioned,
but not otherwise.

### v0.6.0

- [x] Listings, items, offers pagination/iteration
- [x] Get single item from inventory as browser does
- [x] Change client username method

### v0.7.0

- [x] Remove storage methods. Caching entities must be user responsibility
- [x] Rename `fetch_...` methods to `get_...` to remove annoying methods symantic mess
- [x] ~~Web browser mechanism to fetch trade offers from `Steam`, avoiding `Steam Web Api`~~
- [ ] Edit profile privacy settings

### v0.8.0

- [ ] Context managers as helpers to login/logout, load/dump or get/put cookies
- [ ] Fetch/paginate over market search pages

### v0.9.0

- [ ] `Steam user` model with minimal attrs, retrieving/fetching
- [ ] Refresh `access_token` mechanism

### v1.0.0

- [ ] Tests with `Steam API` mocking. Target coverage ~70%. Key points (listings, inventory items, trade offers) testing
suits is mandatory
- [ ] Maturity, battle-testing in **more** different cases by **more** participants/users 

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
