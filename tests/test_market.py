import pytest

from aiosteampy.models import MarketListing


@pytest.mark.incremental
class TestMarketInteractions:
    async def test_get_market_listings(self, client, inventory, context):
        listings, total = await client.get_item_listings(inventory[0], count=10)

        assert listings

        context["listings"] = listings

    async def test_get_wallet_balance(self, client, context):
        listings: list[MarketListing] = context["listings"]
        # make sure that wallet balance is enough to place orders
        balance, cur = await client.get_wallet_balance()

        assert balance > listings[0].converted_price / 1.5

    async def test_place_sell_listing(self, client, inventory, context):
        listings: list[MarketListing] = context["listings"]
        # place sell listing with price of 4 times more than the cheapest listing to ensure that
        # no one will buy our listing during test case time
        listings_id = await client.place_sell_listing(inventory[0], to_receive=listings[0].total_converted_price * 4)
        context["sell_listings_id"] = listings_id

    async def test_place_buy_order(self, client, inventory, context):
        listings: list[MarketListing] = context["listings"]
        # place buy order with price 2 times less than the cheapest listing
        buy_order_id = await client.place_buy_order(
            inventory[0].class_,
            price=listings[0].total_converted_price / 2,
            quantity=1,
        )

        assert buy_order_id

        context["buy_order_id"] = buy_order_id

    async def test_get_my_listings(self, client, inventory, context):
        listings_id: int | None = context["sell_listings_id"]
        buy_order_id: int = context["buy_order_id"]
        active, to_confirm, buy_orders = await client.get_my_listings(page_size=10)

        if listings_id:
            assert listings_id in [l.listing_id for l in active]
        else:
            context["sell_listings_id"] = active[0]  # listing model

        assert buy_order_id in [b.buy_order_id for b in buy_orders]

    async def test_cancel_sell_listing(self, client, context):
        listings: MarketListing | int = context["sell_listings_id"]
        await client.cancel_sell_listing(listings)

    async def test_cancel_buy_order(self, client, context):
        buy_order_id: int = context["buy_order_id"]
        await client.cancel_buy_order(buy_order_id)
