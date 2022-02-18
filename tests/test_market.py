import pytest

from .data import ITEM_DATA, TOTAL_LISTINGS, BUY_ORDERS, SELL_LISTINGS, CURRENCY, GAME


@pytest.mark.asyncio
async def test_get_price(client):
    item = ITEM_DATA
    prices = await client.market.fetch_price(item, GAME)
    assert prices["success"]


@pytest.mark.asyncio
async def test_get_price_history(client):
    item = ITEM_DATA
    response = await client.market.fetch_price_history(item, GAME)
    assert response["success"]
    assert "prices" in response


@pytest.mark.asyncio
async def test_get_all_listings_from_market(client):
    listings = await client.market.get_my_market_listings()
    assert len(listings) == TOTAL_LISTINGS
    assert len(listings.get("buy_orders")) == BUY_ORDERS
    assert len(listings.get("sell_listings")) == SELL_LISTINGS


@pytest.mark.asyncio
async def test_create_and_remove_sell_listing(client):
    inventory = await client.get_my_inventory(GAME)
    asset_id_to_sell = None
    for asset_id, item in inventory.items():
        if item.get("marketable") == 1:
            asset_id_to_sell = asset_id
            break
    assert asset_id_to_sell is not None, "You need at least 1 marketable item to pass this test"
    response = await client.market.create_sell_order(asset_id_to_sell, GAME, "10000")
    assert response["success"]
    sell_listings = (await client.market.get_my_market_listings())["sell_listings"]
    listing_to_cancel = None
    for listing in sell_listings.values():
        if listing["description"]["id"] == asset_id_to_sell:
            listing_to_cancel = listing["listing_id"]
            break
    assert listing_to_cancel is not None
    response = await client.market.cancel_sell_order(listing_to_cancel)
    pass  # for breakpoint


@pytest.mark.asyncio
async def test_create_and_cancel_buy_order(client):
    # PUT THE REAL CURRENCY OF YOUR STEAM WALLET, OTHER CURRENCIES WILL NOT WORK
    response = await client.market.create_buy_order("AK-47 | Redline (Field-Tested)", "10.34", 2, GAME, CURRENCY)
    buy_order_id = response["buy_orderid"]
    assert response["success"] == 1
    assert buy_order_id is not None
    response = await client.market.cancel_buy_order(buy_order_id)
    assert response["success"]
