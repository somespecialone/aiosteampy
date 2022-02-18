import os

from asyncsteampy.models import Currency, GameOptions

ITEM_DATA = "M4A1-S | Cyrex (Factory New)"

# env variables
# TEST_API_KEY
# TEST_LOGIN
# TEST_PASSWORD
# TEST_STEAMID
# TEST_SHARED_SECRET
# TEST_IDENTITY_SECRET
# TEST_PROXY_ADDR = schema://username:password@host:port

CREDENTIALS = {
    "api_key": os.getenv("TEST_API_KEY"),
    "login": os.getenv("TEST_LOGIN"),
    "password": os.getenv("TEST_PASSWORD"),
    "steam_guard": {
        "steamid": os.getenv("TEST_STEAMID"),
        "shared_secret": os.getenv("TEST_SHARED_SECRET"),
        "identity_secret": os.getenv("TEST_IDENTITY_SECRET"),
    },
    "proxy_addr": os.getenv("TEST_PROXY_ADDR"),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 8172.45.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.64 Safari/537.36"
}

TOTAL_LISTINGS = 2
BUY_ORDERS = 0
SELL_LISTINGS = 0

CURRENCY = Currency.RUB
GAME = GameOptions.CSGO
