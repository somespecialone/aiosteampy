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
But now it standalone project. Created by myself for steam trading purposes mostly.

---

[![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner-direct-single.svg)](https://stand-with-ukraine.pp.ua)

<!--header-end-->

---

> **See full documentation [here](https://somespecialone.github.io/aiosteampy) 📖**

---

<!--install-start-->

## Installation

pip

```shell
pip install aiosteampy
```

pipenv

```shell
pipenv install aiosteampy
```

poetry

```shell
poetry add aiosteampy
```

<!--install-end-->

Also, [aiohttp docs](https://docs.aiohttp.org/en/stable/#library-installation) recommends install speedups (`aiodns`
, `cchardet`, ...)

> Old version still available on PyPI: [asyncsteampy](https://pypi.org/project/asyncsteampy/)

---

<!--intro-start-->

AIOSTEAMPY use [aiohttp](https://github.com/aio-libs/aiohttp) underneath to get asynchronous requests to steam servers,
with modern (not really for current moment 😊) async/await syntax.
Project is similar to [Gobot1234/steam.py](https://github.com/Gobot1234/steam.py) for first look, but with some
differences.
It uses only requests and steam apis (documented and not), while `steam.py` implement stateful steam client based on
websocket
protobuf, same as [DoctorMcKay/node-steam-user](https://github.com/DoctorMcKay/node-steam-user).

> Generally, project inspired most
> by [DoctorMcKay/node-steamcommunity](https://github.com/DoctorMcKay/node-steamcommunity)
> but created with additions and differences, of course.

## Key features

* Stateless: the main idea was a low-middle layer API wrapper of some steam services and methods like market,
  tradeoffers, confirmations, steamguard, etc. But if you want to cache your entities data (listings, confirmations,
  ...) there is some methods to help.
* Declarative: there is models almost for every data.
* Typed: for editor support most things are typed.
* Short: I really tried to fit most important for steam trading methods.

## What can I do with this

* Operate with steam trade offers for any manner.
* Sell, buy items on market. Place, cancel orders.
* Login trough steam to 3rd party sites.
* Fetch data from market.
* Manipulate many accounts with proxies for each session.
* Store and load cookies to stay logged in.

## What I can't do

* Chat (at least for now).
* Get apps, packages.
* All, that need connection to CM.
* Interact with game servers (inspect CSGO items, ...).
* Edit profile, social interaction(groups, clans).
* Handle entities(listings, items, tradeoffers) lifecycle for easy if you need to store it.

<!--intro-end-->

---

## Tests 🧪

**Read [test documentation](https://somespecialone.github.io/aiosteampy/tests/) 📖**

---

<!--footer-start-->

## Contribution 💛

There is no rules or requirements to contribute. Feedbacks, suggests, other are welcome.
I will be very grateful for helping me get the things right.

## Credits

* [bukson/steampy](https://github.com/bukson/steampy)
* [DoctorMcKay/node-steamcommunity](https://github.com/DoctorMcKay/node-steamcommunity)
* [Identifying Steam items](https://dev.doctormckay.com/topic/332-identifying-steam-items/)
* [Revadike/InternalSteamWebAPI](https://github.com/Revadike/InternalSteamWebAPI)
* [Gobot1234/steam.py](https://github.com/Gobot1234/steam.py)
* [somespecialone/steam-item-name-ids](https://github.com/somespecialone/steam-item-name-ids)
* [steamapi.xpaw.me](https://steamapi.xpaw.me/)

<!--footer-end-->
