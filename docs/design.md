## Prologue

This project embodies `SteamCommunity` + a small part of the `Steam Web Api`.
Designed to be flexible with modest complexity, while being typed and developer friendly as possible.

> Created mostly for trading purposes, so, I hope, must and will cover most cases for `Steam` trading.

As you can read in [previous](./get_started.md#first-words) chapter, there is two **clients**: public and non-public.
Both represents interaction layer with `SteamCommunity`.
Each **client** instance has separate `session`, therefore as **cookies**, and other properties
(country, currency, ...). 

!!! tip
    Think of them as a private-mode window of a web browser. Each **client** instance is a new private mode window,
    completely independent and separate from others

!!! info "Persistence"
    However, if it is impossible to store session properties from private window of a web browser and then restore 
    from them intentionally, You can do this with `aiosteampy` **client**, both public and non.
    Take a closer look [here](./session.md)

## Points

All interaction with `SteamCommunity` goes through the **client**. Next means that models,
like `EconItem`, `MarketListing`, `TradeOffer` does not have methods to interact with `SteamCommunity`
and do not even know what the **client** is.

!!! info "Web proxy"
    Each client can be connected to a web proxy and make all requests through it. 
    [Proxies](./proxies.md) chapter will tell you more about it.

To give more grain control over requests, whenever it is possible methods have **headers** and
**payload/params** arguments to pass additional info/data to request.

### Community parts

**Client** consist of a methods related to different parts of `SteamCommunity`.
As example, `MarketMixin` responsible for methods related to `SteamMarket`: buying listings, get listings, get orders 
and more, `TradeMixin`, otherwise, responsible for methods related to trade offers: create, counter, decline, ...

So, if you want to augment client behaviour, subclass `SteamClientBase` or `SteamPublicClientBase` for your needs. 
This classes inherit all corresponding mixins. [Inheritance](./client.md#inheritance)

### Exceptions

There is two general types of exceptions: `python` (builtin exceptions, related to invalid arguments values,
broken connection, so on) and `steam`, that raised when code faced error while trying to interact with `Steam`,
as follows: `Steam` cannot return market listings, items not in inventory, malformed response, `Steam`
return error result (`EResult`) deliberately for some reason (lol) or even give your **client** (mainly, by ip) a
rate limit restriction ([more information](./scraping.md)).

### Modules & entrypoints

`Aiosteampy` contains `utils` and `helpers` moduls, each contain useful utilities to make work with **client** easier.
[There is](./utils_helpers.md)

Alongside with mentioned moduls project have a few `extensions`:

- [user agents](./ext/user_agents.md) - service, which main aim is to help get random user agent for your **client/s**
- [currency converter](./ext/converter.md) - service, aims to help you convert `Steam` currencies

## Epilogue

_That's it_. Further information introduce short overview of methods, how things work more detailed and even
hard to say some patterns. Good luck 👋!
