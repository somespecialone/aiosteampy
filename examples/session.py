import asyncio
import json
from pathlib import Path

from aiohttp import ClientSession

cookie_file = Path("cookie.json")


async def main():
    from aiosteampy import SteamClient, Currency
    from aiosteampy.utils import restore_from_cookies, get_jsonable_cookies

    async with ClientSession(raise_for_status=True) as sess:
        client = SteamClient(
            "...",
            "...",
            123456789,
            shared_secret="...",
            identity_secret="...",
            api_key="...",
            trade_token="...",
            wallet_currency=Currency.UAH,
            wallet_country="UA",
            session=sess,
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
                json.dump(get_jsonable_cookies(sess), f)


if __name__ == "__main__":
    import platform

    platform.system() == "Windows" and asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
