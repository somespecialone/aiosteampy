# <p align="center">AIOSteamPY</p>

[![Made in Ukraine](https://img.shields.io/badge/made_in-ukraine-ffd700.svg?labelColor=0057b7)](https://stand-with-ukraine.pp.ua)
[![steam](https://shields.io/badge/steam-1b2838?logo=steam)](https://store.steampowered.com/)
[![license](https://img.shields.io/github/license/somespecialone/aiosteampy)](https://github.com/somespecialone/aiosteampy/blob/master/LICENSE)
[![pypi](https://img.shields.io/pypi/v/aiosteampy)](https://pypi.org/project/aiosteampy)
[![versions](https://img.shields.io/pypi/pyversions/aiosteampy)](https://pypi.org/project/aiosteampy)
[![Tests](https://github.com/somespecialone/aiosteampy/actions/workflows/tests.yml/badge.svg)](https://github.com/somespecialone/aiosteampy/actions/workflows/tests.yml)
[![Publish](https://github.com/somespecialone/aiosteampy/actions/workflows/publish.yml/badge.svg)](https://github.com/somespecialone/aiosteampy/actions/workflows/publish.yml)
[![codecov](https://codecov.io/gh/somespecialone/aiosteampy/branch/master/graph/badge.svg?token=H3JL81SL7P)](https://codecov.io/gh/somespecialone/aiosteampy)
[![CodeFactor](https://www.codefactor.io/repository/github/somespecialone/aiosteampy/badge)](https://www.codefactor.io/repository/github/somespecialone/aiosteampy)
[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> ### Previously this library was a soft fork of [bukson/steampy](https://github.com/bukson/steampy) ⚠ and created only to provide asynchronous methods and proxies support.
> ### But now ...

---

[![Stand With Ukraine](https://raw.githubusercontent.com/vshymanskyy/StandWithUkraine/main/banner-direct-single.svg)](https://stand-with-ukraine.pp.ua)

---

## Navigation 🧾

- [**Installation**](#installation)
- [**Get started 🚀**](#get-started-)
- [**Universes**]()
    - [**Market**]()
    - [**Trade 💱**]()
    - [**Login**]()
    - [**Public**]()
    - [**Utils 🛠**]()
- [**Proxy support**](#proxy-support)
- [**Tests 🧪**](#tests)
- [**Links**](#links)

---

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

## Get started 🚀

## Proxy support

If your proxy type is socks4/5 you should look at this small but precious
library [aiohttp-socks](https://github.com/romis2012/aiohttp-socks), if proxy type http/https, or you don't
like `aiohttp-socks` you can use [aiohttp-proxy](
https://github.com/Skactor/aiohttp-proxy) instead.

```python

```

## Tests 🧪

To run tests clone repo, install with tests

```shell
poetry install --with test
```

Create env variables listed in [tests/data](tests/data.py) and run `pytest` from project dir:

```shell
pytest
```

## Links:

* [DoctorMcKay/node-steamcommunity](https://github.com/DoctorMcKay/node-steamcommunity)
* [Identifying Steam items](https://dev.doctormckay.com/topic/332-identifying-steam-items/)
* [Revadike/InternalSteamWebAPI](https://github.com/Revadike/InternalSteamWebAPI)
* [Gobot1234/steam.py](https://github.com/Gobot1234/steam.py)
* [somespecialone/steam-item-name-ids](https://github.com/somespecialone/steam-item-name-ids)
