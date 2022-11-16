from typing import TYPE_CHECKING
from http.cookies import SimpleCookie
from base64 import b64encode
from time import time as time_time

from rsa import PublicKey, encrypt

from .exceptions import CaptchaRequired, LoginError, ApiError
from .constants import STEAM_URL
from .utils import get_cookie_value_from_session

if TYPE_CHECKING:
    from .client import SteamClient

__all__ = ("LoginMixin", "LOGIN_URL")

LOGIN_URL = STEAM_URL.STORE / "login"


class LoginMixin:
    """
    Mixin with confirmations related methods.
    """

    __slots__ = ()

    _is_logged: bool

    def __init__(self, *args, **kwargs):
        self._is_logged = False

        super().__init__(*args, **kwargs)

    @property
    def is_logged(self) -> bool:
        return self._is_logged

    @property
    def session_id(self: "SteamClient") -> str | None:
        return get_cookie_value_from_session(self.session, STEAM_URL.HELP.host, "sessionid")

    async def is_session_alive(self: "SteamClient") -> bool:
        r = await self.session.get(STEAM_URL.COMMUNITY)
        rt = await r.text()
        return self.username.lower() in rt.lower()

    async def login(self: "SteamClient", *, init_data=True, rsa_retries=5):
        """
        Perform login.

        :param init_data: fetch initial required data (api key, trade token)
        :param rsa_retries: retries to fetch rsa
        :raises ApiError: if failed to fetch rsa for `rsa_retries` times
        :raises LoginError:
        """

        data = await self._do_login(rsa_retries)

        # login redirects
        for url in data["transfer_urls"]:
            await self.session.post(url, data=data["transfer_parameters"])

        c_key = "sessionid"
        for url in (STEAM_URL.STORE, STEAM_URL.COMMUNITY):
            c = SimpleCookie()
            c[c_key] = self.session_id
            c[c_key]["path"] = "/"
            c[c_key]["domain"] = url.host
            c[c_key]["secure"] = True
            c[c_key]["SameSite"] = None

            self.session.cookie_jar.update_cookies(cookies=c, response_url=url)

        init_data and await self._init_data()

        self._is_logged = True

    async def _do_login(self: "SteamClient", rsa_retries: int, two_factor_code="") -> dict[str, ...]:
        pub_key, ts = await self._fetch_rsa_params(rsa_retries)
        data = {
            "password": b64encode(encrypt(self._password.encode("utf-8"), pub_key)).decode(),
            "username": self.username,
            "twofactorcode": two_factor_code,
            "emailauth": "",
            "loginfriendlyname": "",
            "captchagid": "-1",
            "captcha_text": "",
            "emailsteamid": "",
            "rsatimestamp": ts,
            "remember_login": "true",
            "donotcache": str(int(time_time() * 1000)),
        }
        r = await self.session.post(LOGIN_URL / "dologin", data=data)
        rj: dict[str, ...] = await r.json()
        if rj.get("captcha_needed"):
            raise CaptchaRequired  # need to pass args, captcha id, url and something else useful

        if rj["requires_twofactor"]:
            return await self._do_login(rsa_retries, self.two_factor_code)
        elif not rj.get("success"):
            raise LoginError(rj["message"], rj)

        return rj

    async def _fetch_rsa_params(self: "SteamClient", rsa_retries) -> tuple[PublicKey, int]:
        rj = {}
        for _ in range(rsa_retries):
            r = await self.session.post(LOGIN_URL / "getrsakey/", data={"username": self.username})
            rj = await r.json()
            try:
                rsa_mod = int(rj["publickey_mod"], 16)
                rsa_exp = int(rj["publickey_exp"], 16)
                rsa_timestamp = int(rj["timestamp"])

                return PublicKey(rsa_mod, rsa_exp), rsa_timestamp
            except KeyError:
                pass

        raise ApiError("Could not obtain rsa-key.", rj)

    async def logout(self: "SteamClient") -> None:
        await self.session.post(LOGIN_URL / "logout/", data={"sessionid": self.session_id})
        self._is_logged = False
