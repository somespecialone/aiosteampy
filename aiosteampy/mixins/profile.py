from urllib.parse import quote
from re import search as re_search
from json import loads as jloads

from yarl import URL

from ..exceptions import EResultError
from ..constants import STEAM_URL, EResult
from ..typed import ProfileData
from ..utils import to_int_boolean
from .login import LoginMixin


class ProfileMixin(LoginMixin):
    """
    Profile attributes and data related methods.
    Depends on `LoginMixin`.
    """

    __slots__ = ()

    # required instance attributes
    trade_token: str | None

    @property
    def trade_url(self) -> URL | None:
        if self.trade_token:
            return STEAM_URL.TRADE / "new/" % {"partner": self.account_id, "token": self.trade_token}

    @property
    def profile_url(self) -> URL:
        return STEAM_URL.COMMUNITY / f"profiles/{self.steam_id}"

    async def get_profile_url_alias(self) -> URL:
        """Get profile url alias like `https://steamcommunity.com/id/alias`"""

        r = await self.session.get(STEAM_URL.COMMUNITY / "my", allow_redirects=False)
        return URL(r.headers["Location"])

    async def register_new_trade_url(self) -> URL:
        """Register new trade url. Cache token."""

        r = await self.session.post(
            self.profile_url / "tradeoffers/newtradeurl",
            data={"sessionid": self.session_id},
        )
        token: str = await r.json()

        self.trade_token = quote(token, safe="~()*!.'")  # https://stackoverflow.com/a/72449666/19419998
        return self.trade_url

    async def get_trade_token(self) -> str | None:
        """Fetch trade token from `Steam`, cache it and return"""

        r = await self.session.get(self.profile_url / "tradeoffers/privacy")
        rt = await r.text()

        search = re_search(r"\d+&token=(?P<token>.+)\" readonly", rt)
        self.trade_token = search["token"] if search else None
        return self.trade_token

    async def get_profile_data(self, profile_alias: URL = None) -> ProfileData:
        """Fetch profile settings data"""

        if profile_alias is None:
            profile_alias = await self.get_profile_url_alias()
        r = await self.session.get(profile_alias / "edit/info")
        rt = await r.text()

        return jloads(re_search(r"data-profile-edit=\"(.+)\" data-profile-badges", rt)[1].replace("&quot;", '"'))

    async def edit_profile(
        self,
        *,
        persona_name: str = None,
        real_name: str = None,
        summary: str = None,
        country: str = None,
        state: str = None,
        city: str = None,
        custom_url: str = None,
        hide_profile_award: bool = None,
    ):
        """
        Edit profile data

        :param persona_name: nickname
        :param real_name: real name of the user
        :param summary: profile summary
        :param country:
        :param state:
        :param city:
        :param custom_url: custom url `ALIAS` (`https://steamcommunity.com/id/ALIAS`)
        :param hide_profile_award:
        :raises EResultError: for ordinary reasons
        """

        args = [persona_name, real_name, summary, country, state, city, custom_url, hide_profile_award]
        if all(map(lambda x: x is None, args)):
            raise ValueError("You need to pass at least one value")

        profile_alias = await self.get_profile_url_alias()
        profile_data = await self.get_profile_data(profile_alias)

        # https://github.com/DoctorMcKay/node-steamcommunity/blob/1067d4572ee9d467e8f686951901c51028c5c995/components/profile.js#L56
        data = {
            "sessionID": self.session_id,
            "type": "profileSave",
            "hide_profile_awards": "0",
            "json": 1,
            "weblink_1_title": "",
            "weblink_1_url": "",
            "weblink_2_title": "",
            "weblink_2_url": "",
            "weblink_3_title": "",
            "weblink_3_url": "",
            # attr below
            "personaName": persona_name if persona_name is not None else profile_data["strPersonaName"],
            "real_name": real_name if real_name is not None else profile_data["strRealName"],
            "hide_profile_award": to_int_boolean(hide_profile_award)
            if hide_profile_award is not None
            else profile_data["ProfilePreferences"]["hide_profile_awards"],
            "summary": summary if summary is not None else profile_data["strSummary"],
            "country": country if country is not None else profile_data["LocationData"]["locCountryCode"],
            "state": state if state is not None else profile_data["LocationData"]["locStateCode"],
            "city": city if city is not None else profile_data["LocationData"]["locCity"],
            "customURL": custom_url if custom_url is not None else profile_data["strCustomURL"],
        }
        r = await self.session.post(profile_alias / "edit/", data=data)
        rj = await r.json()
        success = EResult(rj.get("success"))
        if success is not EResult.OK:
            raise EResultError(rj.get("message", "Failed to edit profile"), success, rj)

    # async def set_privacy_settings(self):
    #     pass

    # TODO upload avatar
