"""Utils, models and component to work with current user profile."""

import json
import re
from collections.abc import Awaitable
from pathlib import Path

from yarl import URL

from ...constants import STEAM_URL, Currency, EResult, Language
from ...exceptions import EResultError, NeedMobileConfirmation, SteamError
from ...id import SteamID
from ...session import SteamSession
from ...transport import BaseSteamTransport, TransportResponse
from ..state import SteamState
from .models import (
    AvatarUploadData,
    AvatarUploadImagesData,
    CommentPrivacySettingsOptions,
    GoldenProfileDataEntry,
    LocationData,
    MiniProfileBadge,
    MiniProfileData,
    MiniprofileMovie,
    PrivacySettingsOptions,
    ProfileAliasHistoryEntry,
    ProfileData,
    ProfilePreferences,
    ProfilePrivacy,
    ProfilePrivacySettings,
    ProfileTheme,
)
from .public import ProfilePublicComponent

PROFILE_DATA_RE = re.compile(r"data-profile-edit=\"(.+)\" data-profile-badges")


class ProfileComponent(ProfilePublicComponent):
    """Component to work with `Steam` profile."""

    __slots__ = ("_session", "_state")

    def __init__(self, session: SteamSession, state: SteamState):
        super().__init__(session.transport)

        self._session = session
        self._state = state

    @property
    def url(self) -> URL:
        """
        Profile `url` of current user.
        If ``alias`` is set, return `custom url`, e.g `https://steamcommunity.com/id/<ALIAS>`.
        """

        return self._state.profile_url

    async def get_info(self) -> ProfileData:
        """Get current user profile info including general properties and privacy settings."""

        # safe to make GET if alias is not set but existed, redirects will be handled
        r = await self._transport.request("GET", self.url / "edit/info", redirects=True, response_mode="text")

        search = PROFILE_DATA_RE.search(r.content)

        data: dict = json.loads(search.group(1).replace("&quot;", '"'))

        profile_data = ProfileData(
            persona_name=data["strPersonaName"],
            custom_url=data["strCustomURL"],
            real_name=data["strRealName"],
            summary=data["strSummary"],
            avatar_hash=data["strAvatarHash"],
            persona_name_banned_until=data["rtPersonaNameBannedUntil"],
            profile_summary_banned_until=data["rtProfileSummaryBannedUntil"],
            avatar_banned_until=data["rtAvatarBannedUntil"],
            location_data=LocationData(
                city=data["LocationData"]["locCity"],
                city_code=data["LocationData"]["locCityCode"],
                country=data["LocationData"]["locCountry"],
                country_code=data["LocationData"]["locCountryCode"],
                state=data["LocationData"]["locState"],
                state_code=data["LocationData"]["locStateCode"],
            ),
            active_theme=ProfileTheme(data["ActiveTheme"]["theme_id"], data["ActiveTheme"]["title"]),
            profile_preferences=ProfilePreferences(data["ProfilePreferences"]["hide_profile_awards"]),
            available_themes=tuple(ProfileTheme(t_d["theme_id"], t_d["title"]) for t_d in data["rgAvailableThemes"]),
            golden_profile_data=tuple(
                GoldenProfileDataEntry(
                    gp_d["appid"],
                    gp_d["css_url"],
                    gp_d["frame_url"],
                    gp_d["miniprofile_background"],
                    MiniprofileMovie(
                        gp_d["miniprofile_movie"].get("video/webm"),
                        gp_d["miniprofile_movie"].get("video/mp4"),
                    )
                    if gp_d["miniprofile_movie"]
                    else None,
                )
                for gp_d in data["rgGoldenProfileData"]
            ),
            privacy=ProfilePrivacy(
                settings=ProfilePrivacySettings(
                    friends_list=data["Privacy"]["PrivacySettings"]["PrivacyFriendsList"],
                    inventory=data["Privacy"]["PrivacySettings"]["PrivacyInventory"],
                    inventory_gifts=data["Privacy"]["PrivacySettings"]["PrivacyInventoryGifts"],
                    owned_games=data["Privacy"]["PrivacySettings"]["PrivacyOwnedGames"],
                    playtime=data["Privacy"]["PrivacySettings"]["PrivacyPlaytime"],
                    profile=data["Privacy"]["PrivacySettings"]["PrivacyProfile"],
                ),
                comment_permission=data["Privacy"]["eCommentPermission"],
            ),
        )

        self._state._alias = profile_data.custom_url  # implicitly update alias, assuming that's safe

        return profile_data

    async def edit_info(
        self,
        *,
        persona_name: str | None = None,
        real_name: str | None = None,
        summary: str | None = None,
        country: str | None = None,
        state: str | None = None,
        city: str | None = None,
        custom_url: str | None = None,
        hide_profile_award: bool | None = None,
        profile_data: ProfileData | None = None,
    ):
        """
        Edit current user profile general info.

        :param persona_name: nickname.
        :param real_name: real name of the user.
        :param summary: profile summary.
        :param country: profile country code.
        :param state: profile state code.
        :param city: profile city.
        :param custom_url: custom url `ALIAS` (`https://steamcommunity.com/id/<ALIAS>`). E.g. `somespecialone`.
        :param hide_profile_award: whether to hide profile awards.
        :param profile_data: profile data with default values. If not provided, will be fetched from the server.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises ValueError: required arguments not provided.
        """

        if all(
            map(
                lambda x: x is None,
                (persona_name, real_name, summary, country, state, city, custom_url, hide_profile_award),
            )
        ):
            raise ValueError("At least one argument must be provided")

        if profile_data is None:
            profile_data = await self.get_info()  # alias will be updated here

        # https://github.com/DoctorMcKay/node-steamcommunity/blob/1067d4572ee9d467e8f686951901c51028c5c995/components/profile.js#L56
        data = {
            "sessionID": self._session.session_id,
            "type": "profileSave",
            "hide_profile_awards": "0",
            "json": 1,
            "weblink_1_title": "",
            "weblink_1_url": "",
            "weblink_2_title": "",
            "weblink_2_url": "",
            "weblink_3_title": "",
            "weblink_3_url": "",
            # actual attrs below
            "personaName": persona_name if persona_name is not None else profile_data.persona_name,
            "real_name": real_name if real_name is not None else profile_data.real_name,
            "hide_profile_award": (
                int(hide_profile_award)
                if hide_profile_award is not None
                else profile_data.profile_preferences.hide_profile_awards
            ),
            "summary": summary if summary is not None else profile_data.summary,
            "country": country if country is not None else profile_data.location_data.country_code,
            "state": state if state is not None else profile_data.location_data.state_code,
            "city": city if city is not None else profile_data.location_data.city,
            "customURL": custom_url if custom_url is not None else profile_data.custom_url,
        }

        r = await self._transport.request(
            "POST",
            self.url / "edit/",
            data=data,
            headers={"Referer": str(self.url / "edit/settings")},
            response_mode="json",
        )
        rj: dict = r.content

        EResultError.check_data(rj)

    async def edit_privacy_settings(
        self,
        *,
        friends_list: PrivacySettingsOptions | None = None,
        inventory: PrivacySettingsOptions | None = None,
        inventory_gifts: bool | None = None,
        owned_games: PrivacySettingsOptions | None = None,
        playtime: bool | None = None,
        profile: PrivacySettingsOptions | None = None,
        comment_permission: CommentPrivacySettingsOptions | None = None,
        profile_data: ProfileData | None = None,
    ):
        """
        Edit profile privacy settings.

        Privacy levels:
            * 1 - private
            * 2 - friends only
            * 3 - public

        Comment permission levels:
            * 2 - private
            * 0 - friends only
            * 1 - public

        :param friends_list: desired privacy level required to view profile friends list.
        :param inventory: desired `Steam` inventory privacy state.
        :param inventory_gifts: keep profile `Steam` gift inventory private.
        :param owned_games: desired privacy level required to view games current account own and what game is
            currently playing.
        :param playtime: keep game playtime private.
        :param profile: desired general profile privacy state.
        :param comment_permission: desired profile comments privacy state.
        :param profile_data: profile data with default values. If not provided, will be fetched from the server.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        :raises ValueError: required arguments not provided.
        """

        if all(
            map(
                lambda x: x is None,
                (
                    friends_list,
                    inventory,
                    inventory_gifts,
                    owned_games,
                    playtime,
                    profile,
                    comment_permission,
                ),
            )
        ):
            raise ValueError("At least one argument must be provided")

        if profile_data is None:
            profile_data = await self.get_info()  # alias will be updated here

        if friends_list is not None:
            profile_data.privacy.settings.friends_list = friends_list
        if inventory is not None:
            profile_data.privacy.settings.inventory = inventory
        if inventory_gifts is not None:
            profile_data.privacy.settings.inventory_gifts = 3 if inventory_gifts else 1
        if owned_games is not None:
            profile_data.privacy.settings.owned_games = owned_games
        if playtime is not None:
            profile_data.privacy.settings.playtime = 3 if playtime else 1
        if profile is not None:
            profile_data.privacy.settings.profile = profile
        if comment_permission is not None:
            profile_data.privacy.comment_permission = comment_permission

        data = {
            "sessionid": self._session.session_id,
            "Privacy": json.dumps(
                {
                    "PrivacyProfile": profile_data.privacy.settings.profile,
                    "PrivacyInventory": profile_data.privacy.settings.inventory,
                    "PrivacyInventoryGifts": profile_data.privacy.settings.inventory_gifts,
                    "PrivacyOwnedGames": profile_data.privacy.settings.owned_games,
                    "PrivacyPlaytime": profile_data.privacy.settings.playtime,
                    "PrivacyFriendsList": profile_data.privacy.settings.friends_list,
                }
            ),
            "eCommentPermission": comment_permission,
        }

        r = await self._transport.request(
            "POST",
            self.url / "ajaxsetprivacy/",
            data=data,
            headers={"Referer": str(self.url / "edit/settings")},
            response_mode="json",
        )
        rj: dict = r.content

        EResultError.check_data(rj)

    def make_public(self) -> Awaitable[None]:
        """Make current user profile fully public."""

        return self.edit_privacy_settings(
            inventory=3,
            inventory_gifts=True,
            profile=3,
            friends_list=3,
            owned_games=3,
            playtime=True,
            comment_permission=1,
        )

    def make_private(self) -> Awaitable[None]:
        """Make current user profile private."""

        return self.edit_privacy_settings(
            inventory=1,
            inventory_gifts=False,
            owned_games=1,
            playtime=False,
            profile=1,
            comment_permission=2,
            friends_list=1,
        )

    def get_mini_profile(self) -> Awaitable[MiniProfileData]:
        """Get user `miniprofile` data."""
        return self.get_user_mini_profile(self._session.steam_id)

    async def upload_avatar(self, source: Path | URL | bytes) -> AvatarUploadData:
        """
        Replaces current avatar image with a new one.
        ``source`` can be a ``pathlib.Path`` pointing to a file,
        a ``yarl.URL`` as an address to image on a remote source,
        or a binary ``bytes`` buffer.

        :param source: image source.
        :return: avatar upload data.
        :raises EResultError: ordinary reasons.
        :raises TransportError: ordinary reasons.
        """

        if isinstance(source, Path):
            with source.open("rb") as f:
                source = f.read()

        elif isinstance(source, URL):
            r = await self._transport.request("GET", source, response_mode="bytes")
            source = r.content

        data = {
            "type": "player_avatar_image",
            "sId": str(self._session.steam_id.id64),
            "sessionid": self._session.session_id,
            "doSub": "1",
            "json": "1",
            "avatar": source,
        }

        r = await self._transport.request(
            "POST",
            STEAM_URL.COMMUNITY / "actions/FileUploader",
            data=data,
            response_mode="json",
        )
        rj: dict = r.content

        EResultError.check_data(rj)

        return AvatarUploadData(
            rj["hash"],
            AvatarUploadImagesData(
                rj["AvatarUploadImagesData"]["medium"],
                rj["AvatarUploadImagesData"]["full"],
            ),
            rj["message"],
        )

    # TODO move to trade
    def trade_acknowledge(self) -> Awaitable[TransportResponse]:
        """
        Acknowledge *trade protection rules*.
        Required only once before you can make trade offers.
        """

        return self._transport.request(
            "POST",
            STEAM_URL.COMMUNITY / "trade/new/acknowledge",
            data={"sessionid": self._session.session_id, "message": 1},
            headers={"Referer": str(self.url / "tradeoffers/"), "Origin": str(STEAM_URL.COMMUNITY)},
            response_mode="meta",
        )

    def get_name_history(self) -> Awaitable[list[ProfileAliasHistoryEntry]]:
        """
        Get nickname history of current user.

        :return: list of profile alias history.
        :raises TransportError: ordinary reasons.
        """

        return self.get_user_name_history(self._session.steam_id)

    def clear_name_history(self) -> Awaitable[TransportResponse]:
        """Clear nickname history of current user."""

        return self._transport.request(
            "POST",
            self.url / "ajaxclearaliashistory",
            data={"sessionid": self._session.session_id},
            response_mode="meta",
        )
