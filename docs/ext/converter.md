# Currencies converter

A `dict-like` class to handle converting steam currencies.

!!! note ""
    Instance is an API consumer of [SERT](https://github.com/somespecialone/sert) and use service endpoints.

## Installation

You can install `converter` with `aiosteampy[converter]` install target. For instance:

```shell
poetry add aiosteampy[converter]
```

## Creating instance and loading rates

Before start converting rates need to be loaded.

```python
from aiosteampy.converter import CurrencyConverter

converter = CurrencyConverter()
await converter.load()
```

## Converting

Assuming that rates loaded we can convert prices of the items on steam market.

!!! info "Target currency"
    Default target converted currency is `USD` but You can pass target currency as third argument

```python
from aiosteampy import Currency

amount_in_usd = converter.convert(14564, Currency.UAH)

# if You need different target currency
amount_in_eur = converter.convert(14564, Currency.UAH, Currency.EUR)
```

## Updating rates

Service update rates frequently and to synchronize rates with it You can use `synchronize` method of the instance.
This will create and run a coroutine wrapped in `asyncio.Task` in the background.

!!! warning "croniter"
    This functionality requires [croniter](https://github.com/kiorky/croniter) library to work, which will be already installed with `aiosteampy[converter]`

```python
converter.synchronize()
```

### Graceful shutdown

In that case You need to `close` instance and handle canceling `_sync_task` before shutdown Your application:

```python
converter.close()
```

## Available currencies

You can see available currencies in [converter web app](https://converter.somespecial.one/).
Just in case You need more or different currencies you can host the service by yourself and pass `api_url` argument to instance.

```python
from yarl import URL

my_api_url = URL("https://mydomain.com")

converter = CurrencyConverter(api_url=my_api_url)
```
