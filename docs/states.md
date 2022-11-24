This is the example of how to override methods(hooks) to cache data in memory on instance attrs.

Caching and removing from cache `confirmations` work fine, but, unfortunately, there is pitfalls with `tradeoffers`.
There is no way to handle full lifecycle of `tradeoffers` without periodically poll changes from `steam web api` 
(good one idea is for trigger filling trades with [get_notifications](https://github.com/somespecialone/aiosteampy/blob/master/aiosteampy/client.py)
client method).

> But I hope I do some of this in near future in other project which will be more suitable for trading and be middle-high layer over of and based on this project
> like [DoctorMcKay/node-steam-tradeoffer-manager](https://github.com/DoctorMcKay/node-steam-tradeoffer-manager) on 
> [DoctorMcKay/node-steam-user](https://github.com/DoctorMcKay/node-steam-user).

> Or not, who knows 😶

!!! tip "Where is hooks"
    To see where hooks were called check [TradeMixin](https://github.com/somespecialone/aiosteampy/blob/master/aiosteampy/trade.py)
    and [ConfirmationMixin](https://github.com/somespecialone/aiosteampy/blob/master/aiosteampy/confirmation.py)

!!! info ""
    [**Example here**](./examples/states.md)
