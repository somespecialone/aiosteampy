from yarl import URL

from ...constants import STEAM_URL
from ...id import SteamID


def make_alias_profile_url(alias: str) -> URL:
    return STEAM_URL.COMMUNITY / f"id/{alias}"


def make_steam_id_profile_url(steam_id: SteamID) -> URL:
    return STEAM_URL.COMMUNITY / f"profiles/{steam_id.id64}"
