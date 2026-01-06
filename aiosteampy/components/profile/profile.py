"""Utils, models and component to work with current user profile."""

import re
import json

from dataclasses import asdict
from urllib.parse import quote
from pathlib import Path
from datetime import datetime

from yarl import URL

from ...types import CORO
from ...constants import STEAM_URL, EResult, Language
from ...exceptions import EResultError
from ...id import SteamID
from ...transport import BaseSteamTransport, TransportResponse

from .models import (
    PrivacySettingsOptions,
    CommentPrivacySettingsOptions,
    LocationData,
    ProfilePrivacySettings,
    ProfilePrivacy,
    ProfileTheme,
    ProfilePreferences,
    MiniprofileMovie,
    GoldenProfileDataEntry,
    ProfileData,
    AvatarUploadImagesData,
    AvatarUploadData,
)

TRADE_TOKEN_RE = re.compile(r"\d+&token=(.+)\" readonly")
PROFILE_DATA_RE = re.compile(r"data-profile-edit=\"(.+)\" data-profile-badges")


class ProfileComponent:
    """Component to work with current user `Steam` profile."""

    def __init__(self, transport: BaseSteamTransport, steam_id: SteamID, trade_token: str | None = None):
        self._transport = transport
        self._steam_id = steam_id
        self._trade_token = trade_token
        #  profile custom url attribute is not needed now

    @property
    def steam_id(self) -> SteamID:
        return self._steam_id

    @property
    def transport(self) -> BaseSteamTransport:
        return self._transport

    @property
    def trade_token(self) -> str | None:
        return self._trade_token

    @property
    def trade_url(self) -> URL | None:
        """Trade url for current user."""
        if self._trade_token:
            return STEAM_URL.TRADE / "new/" % {"partner": self._steam_id.account_id, "token": self._trade_token}

    @property
    def profile_url(self) -> URL:
        return STEAM_URL.COMMUNITY / f"profiles/{self._steam_id.id64}"

    async def get_profile_custom_url(self) -> URL:
        """Get profile custom url, e.g `https://steamcommunity.com/id/<ALIAS>`."""

        r = await self._transport.request("GET", STEAM_URL.COMMUNITY / "my", redirects=False, response_mode="meta")
        return URL(r.headers["Location"])

    async def get_trade_token(self) -> str | None:
        """Get trade token from `Steam`. Will set trade token to component."""

        r = await self._transport.request("GET", self.profile_url / "tradeoffers/privacy", response_mode="text")

        search = TRADE_TOKEN_RE.search(r.content)
        self._trade_token = search.group(1) if search else None

        return self.trade_token

    async def register_new_trade_url(self):
        """Register new trade url. Will set trade token to component."""

        r = await self.transport.request(
            "POST",
            self.profile_url / "tradeoffers/newtradeurl",
            data={"sessionid": self._transport.session_id},
            response_mode="json",
        )

        self._trade_token = quote(r.content, safe="~()*!.'")  # https://stackoverflow.com/a/72449666/19419998

    async def get_profile_data(self, profile_custom_url: URL | None = None) -> ProfileData:
        """Get current user profile data including general properties and privacy settings."""

        if profile_custom_url is None:
            profile_custom_url = await self.get_profile_custom_url()

        r = await self._transport.request("GET", profile_custom_url / "edit/info", response_mode="text")

        search = PROFILE_DATA_RE.search(r.content)

        data: dict = json.loads(search.group(1).replace("&quot;", '"'))

        return ProfileData(
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
            available_themes=[ProfileTheme(t_d["theme_id"], t_d["title"]) for t_d in data["rgAvailableThemes"]],
            golden_profile_data=[
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
            ],
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

    async def edit_profile(
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
        _profile_custom_url: URL | None = None,
    ):
        """
        Edit current user profile general data.

        :param persona_name: nickname.
        :param real_name: real name of the user.
        :param summary: profile summary.
        :param country: profile country code.
        :param state: profile state code.
        :param city: profile city.
        :param custom_url: custom url `ALIAS` (`https://steamcommunity.com/id/<ALIAS>`). E.g. `SomeSpecialOne`.
        :param hide_profile_award: whether to hide profile awards.
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises ValueError: required arguments not provided.
        """

        if all(
            map(
                lambda x: x is None,
                [persona_name, real_name, summary, country, state, city, custom_url, hide_profile_award],
            )
        ):
            raise ValueError("At least one argument must be provided")

        if _profile_custom_url is None:
            _profile_custom_url = await self.get_profile_custom_url()

        profile_data = await self.get_profile_data(_profile_custom_url)

        # https://github.com/DoctorMcKay/node-steamcommunity/blob/1067d4572ee9d467e8f686951901c51028c5c995/components/profile.js#L56
        data = {
            "sessionID": self._transport.session_id,
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

        headers = {"Referer": str(_profile_custom_url / "edit/settings")}
        r = await self._transport.request(
            "POST",
            _profile_custom_url / "edit/",
            data=data,
            headers=headers,
            response_mode="json",
        )
        rj: dict = r.content

        if (success := EResult(rj.get("success"))) is not EResult.OK:
            raise EResultError(success, rj.get("message", ""))

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
        _profile_custom_url: URL | None = None,
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
        :raises EResultError: ordinary reasons.
        :raises TransportError: arbitrary reasons.
        :raises ValueError: required arguments not provided.
        """

        if all(
            map(
                lambda x: x is None,
                [
                    friends_list,
                    inventory,
                    inventory_gifts,
                    owned_games,
                    playtime,
                    profile,
                    comment_permission,
                ],
            )
        ):
            raise ValueError("At least one argument must be provided")

        if _profile_custom_url is None:
            _profile_custom_url = await self.get_profile_custom_url()

        profile_data = await self.get_profile_data(_profile_custom_url)

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
            "sessionid": self._transport.session_id,
            "Privacy": json.dumps(asdict(profile_data.privacy.settings)),
            "eCommentPermission": comment_permission,
        }
        headers = {"Referer": str(_profile_custom_url / "edit/settings")}

        r = await self._transport.request(
            "POST",
            _profile_custom_url / "ajaxsetprivacy/",
            data=data,
            headers=headers,
            response_mode="json",
        )
        rj: dict = r.content

        if (success := EResult(rj.get("success"))) is not EResult.OK:
            raise EResultError(success, rj.get("message", ""))

    async def upload_avatar(self, source: Path | URL | bytes) -> AvatarUploadData:
        """
        Replaces current avatar image with a new one.
        ``source`` can be a ``pathlib.Path`` pointing to a file,
        a ``yarl.URL`` as an address to image on a remote source,
        or a binary ``bytes`` buffer.
        """

        if isinstance(source, Path):
            with source.open("rb") as f:
                source = f.read()

        elif isinstance(source, URL):
            r = await self.transport.request("GET", source, response_mode="bytes")
            source = r.content

        data = {
            "type": "player_avatar_image",
            "sId": str(self.steam_id.id64),
            "sessionid": self._transport.session_id,
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

        if (success := EResult(rj.get("success"))) is not EResult.OK:
            raise EResultError(success, rj.get("message", ""))

        return AvatarUploadData(
            rj["hash"],
            AvatarUploadImagesData(
                rj["AvatarUploadImagesData"]["medium"],
                rj["AvatarUploadImagesData"]["full"],
            ),
            rj["message"],
        )

    # TODO move to trade
    def trade_acknowledge(self) -> CORO[TransportResponse]:
        """
        Acknowledge *trade protection rules*.
        Required only once before you can make trade offers.
        """

        headers = {"Referer": str(self.profile_url / "tradeoffers/"), "Origin": str(STEAM_URL.COMMUNITY)}
        data = {"sessionid": self._transport.session_id, "message": 1}

        return self._transport.request(
            "POST",
            STEAM_URL.COMMUNITY / "trade/new/acknowledge",
            data=data,
            headers=headers,
            response_mode="meta",
        )

    # TODO this may be insufficient to force language change, look at lang preferences in profile settings
    def set_language(self, lang: Language) -> CORO[TransportResponse]:
        """
        Set language of steam community and other domains.

        .. note:: Language other than English will break some methods.
        """

        data = {"sessionid": self._transport.session_id, "language": lang.value}
        return self._transport.request("POST", STEAM_URL.COMMUNITY / "actions/SetLanguage", data=data)
