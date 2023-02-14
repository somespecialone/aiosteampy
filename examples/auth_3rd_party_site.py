from aiosteampy import SteamClient
from aiosteampy.utils import do_session_steam_auth


async def lootfarm_auth():
    client = SteamClient("...", "...", 123456789, shared_secret="...", identity_secret="...")
    await client.login()

    await do_session_steam_auth(client.session, "https://loot.farm/steam_auth.php")
    # your logged in!

if __name__ == "__main__":
    import asyncio
    import platform

    platform.system() == "Windows" and asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(lootfarm_auth())
