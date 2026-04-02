from datetime import datetime

from ...constants import STEAM_URL
from ...id import SteamID
from .._base import BasePublicComponent
from .models import MiniProfileBadge, MiniProfileData, ProfileAliasHistoryEntry

PROFILE_ALIAS_TIME_FORMAT = "%d %b, %Y @ %I:%M%p"


class ProfilePublicComponent(BasePublicComponent):
    """Component responsible for working with `Steam` profile and related data."""

    __slots__ = ()

    async def get_user_mini_profile(self, user_id: SteamID) -> MiniProfileData:
        """
        Get user `miniprofile` data.

        :param user_id: ``SteamID`` of user.
        :return: `miniprofile` data.
        :raises TransportError: ordinary reasons.
        """

        r = await self._transport.request(
            "GET",
            STEAM_URL.COMMUNITY / f"miniprofile/{user_id.account_id}/json/",
            params={"origin": str(STEAM_URL.COMMUNITY)},
            response_mode="json",
        )

        rj: dict = r.content

        return MiniProfileData(
            avatar=rj["avatar_url"],
            favorite_badge=MiniProfileBadge(
                description=rj["favorite_badge"]["description"],
                icon=rj["favorite_badge"]["icon"],
                level=rj["favorite_badge"]["level"],
                name=rj["favorite_badge"]["name"],
                xp=rj["favorite_badge"]["xp"],
            )
            if rj.get("favorite_badge")
            else None,
            level=rj["level"],
            level_class=rj["level_class"],
            persona_name=rj["persona_name"],
        )

    async def get_user_name_history(self, obj: SteamID | str) -> list[ProfileAliasHistoryEntry]:
        """
        Get nickname history of user.

        :param obj: ``SteamID`` or profile `alias`.
        :return: list of profile `alias` history.
        :raises TransportError: ordinary reasons.
        """

        if isinstance(obj, str):  # alias
            url = STEAM_URL.COMMUNITY / f"id/{obj}"
        else:
            url = STEAM_URL.COMMUNITY / f"profiles/{obj}"

        r = await self._transport.request("GET", url / "ajaxaliases", redirects=True, response_mode="json")

        rj: list[dict] = r.content

        return [
            ProfileAliasHistoryEntry(
                data["newname"],
                datetime.strptime(data["timechanged"], PROFILE_ALIAS_TIME_FORMAT),
            )
            for data in rj
        ]

    # TODO query locations
    # https://steamcommunity.com/actions/QueryLocations/
    # https://steamcommunity.com/actions/QueryLocations/UA/
    # https://steamcommunity.com/actions/QueryLocations/UA/05
