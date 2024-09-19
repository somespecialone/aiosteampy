import asyncio
import json
from pathlib import Path

cookie_file = Path("cookie.json")


async def main():
    from aiosteampy import SteamClient, Currency
    from aiosteampy.helpers import restore_from_cookies
    from aiosteampy.utils import get_jsonable_cookies

    client = SteamClient(
        steam_id=123456789,
        username="...",
        password="...",
        shared_secret="...",
        identity_secret="...",
        api_key="...",
        trade_token="...",
        wallet_currency=Currency.UAH,
        wallet_country="UA",
        proxy="socks5://username:pass@host:port",
    )

    if cookie_file.is_file():
        with cookie_file.open("r") as f:
            cookies = json.load(f)
        await restore_from_cookies(cookies, client)
    else:
        await client.login()

    try:
        ...  # do what you want

    finally:
        with cookie_file.open("w") as f:
            json.dump(get_jsonable_cookies(client.session), f)

        await client.session.close()


if __name__ == "__main__":
    import platform

    platform.system() == "Windows" and asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
