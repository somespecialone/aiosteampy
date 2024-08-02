!!! warning "Current tests are deprecated"
    Test cases and test code as a whole are deprecated and will not work until they are updated (a lot of work).
    I'll leave the code and this heading here as a reminder 🫣

Firstly, almost all test are integration and incremental test. Mocking steam responses and validation
passed query params with payload data would be much, much more complicated than real requests-responses to `steam`.

Secondly, for now test session can not clear all what she has done. This may lead to "hanging" sell listings and buy
orders
if test case failed on some point. It means you must cancel it by `yourself` (if you want, of course, no one forces you
to do this 🙂).

So ...

To run tests you need to clone repo, install project deps with tests:

```shell
poetry install --with test
```

There is mandatory `ENV variables` that need to be filled before start test session:

* `TEST_USERNAME`
* `TEST_PASSWORD`
* `TEST_STEAMID`
* `TEST_SHARED_SECRET`
* `TEST_IDENTITY_SECRET`

And optional:

* `TEST_GAME_APP_ID` - app id of the game which inventory item will be placed on market sell listing
  and for which item type will be created buy order. Default game is `CSGO`.
* `TEST_GAME_CONTEXT_ID` - context id of that game.
* `TEST_ASSET_ID` - asset id of item in inventory if you want to choose one.
* `TEST_COOKIE_FILE_PATH` - string path to json serialized cookies file via
  [utils/get_jsonable_cookies](https://github.com/somespecialone/aiosteampy/blob/master/aiosteampy/utils.py).

!!! info ""
    All env variables listed in [tests/data](https://github.com/somespecialone/aiosteampy/blob/master/tests/data.py)

!!! warning "Requirements"
    You need at least `one marketable item` in passed or default game inventory!
    Wallet balance of account need to be `no less than x1.5` than the cheapest listing of dedicated item type on market,
    to ensure that steam will place buy order.

!!! danger "Items on market"
    Market tests will place sell order for your item on market with `x4 more` price than the price without fee of the
    cheapest market listing for that item type. There is a small, near zero, chance that someone will buy this item.
    If that happens - I suggest you to calculate the profit and chill out 🤑.
    Buy order test, in oppose, will place order for `x1.5 less` price than the cheapest listing.

Now you can run all tests with:

```shell
pytest
```
