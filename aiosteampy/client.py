from time import time as time_time
from http.cookies import SimpleCookie
from re import compile
from urllib.parse import quote
from base64 import b64encode

from rsa import PublicKey, encrypt
from aiohttp import ClientSession
from yarl import URL

from .guard import SteamGuardMixin
from .confirmation import ConfirmationMixin
from .inventory import InventoryMixin
from .market import MarketMixin

from .models import STEAM_URL, Currency
from .exceptions import CaptchaRequired, LoginError, ApiError
from .utils import get_cookie_value_from_session

__all__ = ("SteamClient",)

_WALLET_REGEX = compile(r"account/history/\">(?P<cur>\D)?(?P<balance>\d*[.,]?[\d-]*)\s?(?P<cur1>\W|\w+)?\.?</a")
_API_KEY_REGEX = compile(r"<p>Key: (?P<api_key>[0-9A-F]+)</p>")
_STEAM_ID_REGEX = compile(r"Steam ID: (?P<steam_id>\d+)</")
_TRADE_TOKEN_REGEX = compile(r"\d+&token=(?P<token>.+)\" readonly")

_API_KEY_CHECK_STR = "<h2>Access Denied</h2>"
_API_KEY_CHECK_STR1 = "You must have a validated email address to create a Steam Web API key"


class SteamClient(SteamGuardMixin, ConfirmationMixin, InventoryMixin, MarketMixin):
    """ """

    __slots__ = (
        "_is_logged",
        "session",
        "username",
        "steam_id",
        "_password",
        "_shared_secret",
        "_identity_secret",
        "_api_key",
        "trade_token",
        "_device_id",
        "_confirmations",
        "_inventories",  # do I need states?
        "_orders",
        "_tradeoffers",
    )

    def __init__(
        self,
        username: str,
        password: str,
        steam_id: int = None,
        *,
        shared_secret: str,
        identity_secret: str,
        api_key: str = None,
        trade_token: str = None,
        session: ClientSession = None,
    ):
        super().__init__()
        self._is_logged = False

        self.session = session or ClientSession(raise_for_status=True)
        # TODO admit about raise for status and strange behaviour if opposite in docs.
        self.username = username
        self.steam_id = steam_id  # steam id64
        self.trade_token = trade_token

        self._password = password
        self._shared_secret = shared_secret
        self._identity_secret = identity_secret
        self._api_key = api_key

        if steam_id:
            self._device_id = self._gen_device_id()

    @property
    def is_logged(self) -> bool:
        return self._is_logged

    @property
    def steam_id32(self) -> int | None:
        return (self.steam_id & 0xFFFFFFFF) if self.steam_id else None

    @property
    def trade_url(self) -> URL | None:
        if self.trade_token and self.steam_id:
            return (STEAM_URL.COMMUNITY / "tradeoffer/new/").with_query(
                {"partner": self.steam_id32, "token": self.trade_token}
            )

    @property
    def session_id(self) -> str | None:
        return get_cookie_value_from_session(self.session, STEAM_URL.HELP.host, "sessionid")

    async def _init_data(self):
        if not self._api_key:
            self._api_key = await self._fetch_api_key()
            not self._api_key and await self.register_new_api_key()

        if not self.steam_id:
            self.steam_id = await self._fetch_steamid()
            self._device_id = self._gen_device_id()

        if not self.trade_token:
            self.trade_token = await self._fetch_trade_token()

    async def _fetch_steamid(self) -> int:
        resp = await self.session.get(STEAM_URL.STORE / "account/store_transactions/")
        resp_text = await resp.text()
        return int(_STEAM_ID_REGEX.search(resp_text)["steam_id"])

    async def get_wallet_balance(self) -> tuple[float, Currency | None]:
        """
        Fetch wallet balance and currency(if possible).
        :return: tuple of balance and currency
        """
        resp = await self.session.get(STEAM_URL.STORE / "account/store_transactions/")
        resp_text = await resp.text()
        search = _WALLET_REGEX.search(resp_text)
        return float(search["balance"].replace(",", ".").replace("-", "0")), Currency.by_symbol(
            search["cur"] or search["cur1"]
        )

    async def register_new_trade_url(self) -> URL:
        """
        Register new trade url, set token to attr and return.
        :return: trade url
        """
        resp = await self.session.post(
            STEAM_URL.COMMUNITY / f"profiles/{self.steam_id}/tradeoffers/newtradeurl",
            data={"sessionid": self.session_id},
        )
        resp_json: str = await resp.json()

        self.trade_token = quote(resp_json, safe="~()*!.'")  # https://stackoverflow.com/a/72449666/19419998
        return self.trade_url

    async def _fetch_trade_token(self) -> str | None:
        resp = await self.session.get(STEAM_URL.COMMUNITY / f"profiles/{self.steam_id}/tradeoffers/privacy")
        resp_text = await resp.text()

        search = _TRADE_TOKEN_REGEX.search(resp_text)
        return search["token"] if search else None

    async def _fetch_api_key(self) -> str | None:
        # https://github.com/Gobot1234/steam.py/blob/main/steam/http.py#L208

        resp = await self.session.get(STEAM_URL.COMMUNITY / "dev/apikey")
        resp_text = await resp.text()
        if _API_KEY_CHECK_STR in resp_text or _API_KEY_CHECK_STR1 in resp_text:
            raise ApiError(_API_KEY_CHECK_STR1)

        search = _API_KEY_REGEX.search(resp_text)
        return search["api_key"] if search else None

    async def register_new_api_key(self, domain=STEAM_URL.COMMUNITY.host) -> str:
        """
        Registers new api key, set it to attr and return.
        :param domain: On which domain api key will be registered. Default - steamcommunity
        :return: api key
        """
        # https://github.com/Gobot1234/steam.py/blob/main/steam/http.py#L208

        payload = {
            "domain": domain,
            "agreeToTerms": "agreed",
            "sessionid": self.session_id,
            "Submit": "Register",
        }
        resp = await self.session.post(STEAM_URL.COMMUNITY / "dev/registerkey", data=payload)
        resp_text = await resp.text()

        self._api_key = _API_KEY_REGEX.search(resp_text)["api_key"]
        return self._api_key

    async def is_session_alive(self) -> bool:
        resp = await self.session.get(STEAM_URL.COMMUNITY)
        text_resp = await resp.text()
        return self.username.lower() in text_resp.lower()

    async def login(self, *, init_data=True, rsa_retries=5):
        resp_json = await self._do_login(rsa_retries)

        # login redirects
        for url in resp_json["transfer_urls"]:
            await self.session.post(url, data=resp_json["transfer_parameters"])

        cookie_key = "sessionid"
        for domain in (STEAM_URL.STORE.host, STEAM_URL.COMMUNITY.host):
            cookie = SimpleCookie()
            cookie[cookie_key] = self.session_id
            cookie[cookie_key]["path"] = "/"
            cookie[cookie_key]["domain"] = domain
            cookie[cookie_key]["secure"] = True
            cookie[cookie_key]["SameSite"] = None

            self.session.cookie_jar.update_cookies(cookies=cookie, response_url=URL(domain))

        init_data and await self._init_data()

        self._is_logged = True

    async def _do_login(self, rsa_retries: int, two_factor_code="") -> dict[str, ...]:
        public_key, timestamp = await self._fetch_rsa_params(rsa_retries)
        data = {
            "password": b64encode(encrypt(self._password.encode("utf-8"), public_key)).decode(),
            "username": self.username,
            "twofactorcode": two_factor_code,
            "emailauth": "",
            "loginfriendlyname": "",
            "captchagid": "-1",
            "captcha_text": "",
            "emailsteamid": "",
            "rsatimestamp": timestamp,
            "remember_login": "true",
            "donotcache": str(int(time_time() * 1000)),
        }
        resp = await self.session.post(STEAM_URL.STORE / "login/dologin", data=data)
        resp_json: dict[str, ...] = await resp.json()
        if resp_json.get("captcha_needed"):
            raise CaptchaRequired

        if resp_json["requires_twofactor"]:
            return await self._do_login(rsa_retries, self.two_factor_code)
        elif not resp_json["success"]:
            raise LoginError(resp_json["message"], resp_json)

        return resp_json

    async def _fetch_rsa_params(self, rsa_retries) -> tuple[PublicKey, int]:
        resp_json = {}
        for _ in range(rsa_retries):
            resp = await self.session.post(STEAM_URL.STORE / "login/getrsakey/", data={"username": self.username})
            resp_json = await resp.json()
            try:
                rsa_mod = int(resp_json["publickey_mod"], 16)
                rsa_exp = int(resp_json["publickey_exp"], 16)
                rsa_timestamp = int(resp_json["timestamp"])

                return PublicKey(rsa_mod, rsa_exp), rsa_timestamp
            except KeyError:
                pass

        raise ApiError("Could not obtain rsa-key", resp_json)

    async def logout(self) -> None:
        await self.session.post(STEAM_URL.STORE / "login/logout/", data={"sessionid": self.session_id})
        self._is_logged = False

    async def get_notifications_count(self):
        headers = {"Referer": str(STEAM_URL.COMMUNITY / f"profiles/{self.steam_id}")}
        resp = await self.session.get(STEAM_URL.COMMUNITY / "actions/GetNotificationCounts", headers=headers)
        resp_json = await resp.json()
        # {"notifications":{"4":0,"5":0,"6":0,"8":0,"9":0,"1":0,"2":0,"3":0,"10":0,"11":0}}
        # TODO decode what this means, check js.
