import decimal

import pytest

from asyncsteampy.models import GameOptions


@pytest.mark.asyncio
async def test_is_session_alive(client):
    assert await client.is_session_alive()


@pytest.mark.asyncio
async def test_get_my_inventory(client):
    inventory = client.get_my_inventory(GameOptions.CS)
    assert inventory is not None


@pytest.mark.asyncio
async def test_get_trade_offers_summary(client):
    summary = await client.get_trade_offers_summary()
    assert summary is not None


@pytest.mark.asyncio
async def test_get_trade_offers(client):
    offers = await client.get_trade_offers()
    assert offers is not None


@pytest.mark.asyncio
async def test_get_wallet_balance(client):
    wallet_balance = await client.get_wallet_balance()
    assert isinstance(wallet_balance, decimal.Decimal)
    wallet_balance = await client.get_wallet_balance(convert_to_decimal=False)
    assert isinstance(wallet_balance, str)
