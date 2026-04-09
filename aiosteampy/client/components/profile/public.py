from datetime import datetime

from ....constants import SteamURL
from ....id import SteamID
from ....transport import BaseSteamTransport
from ....webapi.client import COMMUNITY_ORIGIN
from .models import MiniProfileBadge, MiniProfileData, ProfileAliasHistoryEntry

PROFILE_ALIAS_TIME_FORMAT = "%d %b, %Y @ %I:%M%p"


class ProfilePublicComponent:
    """Component responsible for working with `Steam` profile and related data."""

    __slots__ = ("_transport",)

    def __init__(self, transport: BaseSteamTransport):
        self._transport = transport

    async def get_user_mini_profile(self, user_id: SteamID) -> MiniProfileData:
        """
        Get user `miniprofile` data.

        :param user_id: ``SteamID`` of user.
        :return: `miniprofile` data.
        :raises TransportError: ordinary reasons.
        """

        r = await self._transport.request(
            "GET",
            SteamURL.COMMUNITY / f"miniprofile/{user_id.account_id}/json/",
            params={"origin": COMMUNITY_ORIGIN},
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
            url = SteamURL.COMMUNITY / f"id/{obj}"
        else:
            url = SteamURL.COMMUNITY / f"profiles/{obj}"

        r = await self._transport.request("GET", url / "ajaxaliases", redirects=True, response_mode="json")

        rj: list[dict] = r.content

        return [
            ProfileAliasHistoryEntry(
                data["newname"],
                datetime.strptime(data["timechanged"], PROFILE_ALIAS_TIME_FORMAT),
            )
            for data in rj
        ]
