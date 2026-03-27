"""Component responsible for managing user account state."""

import asyncio
import json
import re
from contextlib import suppress
from datetime import datetime
from typing import NamedTuple
from urllib.parse import quote

from yarl import URL

from ..constants import STEAM_URL, Currency, EResult, Language
from ..exceptions import EResultError, NeedMobileConfirmation, SteamError
from ..guard.confirmation import Confirmation, SteamConfirmations
from ..session import SteamSession
from ..transport import BaseSteamTransport, Cookie, format_http_date

LANG_COOKIE = "Steam_Language"

TRADE_TOKEN_RE = re.compile(r"\d+&token=(.+)\" readonly")

API_KEY_RE = re.compile(r"<p>Key: ([0-9A-F]+)</p>")
API_KEY_ERROR_RE = re.compile(r"<div id=\"bodyContents_lo\">\s+?<p>(.+)</p>")

WALLET_INFO_RE = re.compile(r"g_rgWalletInfo = (.+);")


# single source of truth
# TODO need load/dump methods
class PublicStateComponent:
    __slots__ = ("_transport", "_country", "_currency", "_language")

    def __init__(
        self,
        transport: BaseSteamTransport,
        *,
        country: str = "UA",
        currency: Currency = Currency.USD,
        language: Language = Language.ENGLISH,
    ):
        """"""

        self._transport = transport
        self._country = country
        self._currency = currency

        self._language = language  # will be doubled in cookie just like session id
        self._set_language_cookie(language)

    @property
    def country(self) -> str:
        """Country of data requested from `Steam`."""
        return self._country

    @property
    def currency(self) -> Currency:
        """Currency of data requested from `Steam`."""
        return self._currency

    @property
    def language(self) -> Language:
        """Language of `Steam` responses, descriptions, et cetera."""
        return self._language

    def _set_language_cookie(self, lang: Language):
        for domain in (STEAM_URL.COMMUNITY, STEAM_URL.STORE):
            self._transport.add_cookie(
                Cookie(
                    LANG_COOKIE,
                    lang.value,
                    domain=domain.host,
                    # expires in (365 * 5) - 1 days, but we don't need it
                    host_only=True,
                    same_site="None",
                    secure=True,
                )
            )

    def set_language(self, lang: Language):
        """
        Set main `language` of `Steam` domains.

        Language other than `English` will **break some methods and lead to unexpected behavior**.
        """

        # browser behavior:
        # POST https://store.steampowered.com/account/setlanguage/ json=language, sessionid
        # POST  https://steamcommunity.com/actions/SetLanguage/ json=language, sessionid
        # all work from above just to set cookies, so we can bypass requests and set it manually

        self._set_language_cookie(lang)


class WalletInfo(NamedTuple):
    wallet_currency: Currency
    wallet_country: str
    wallet_state: str
    wallet_fee: int
    wallet_fee_minimum: int
    wallet_fee_percent: float
    wallet_publisher_fee_percent_default: float
    wallet_fee_base: int
    wallet_balance: int
    wallet_delayed_balance: int
    wallet_max_balance: int
    wallet_trade_max_balance: int


class StateComponent(PublicStateComponent):
    __slots__ = (
        "_session",
        "_conf",
        "_web_api_key",
        "_trade_token",
        "_alias",
        "_steam_fee",
        "_publisher_fee",
        "_fee_min",
        "_fee_base",
    )

    def __init__(
        self,
        session: SteamSession,
        confirmations: SteamConfirmations | None = None,
        *,
        country: str = "UA",
        currency: Currency = Currency.USD,
        language: Language = Language.ENGLISH,
        web_api_key: str | None = None,
        trade_token: str | None = None,
        alias: str | None = None,
    ):
        """

        :param session:
        :param confirmations:
        :param country:
        :param currency:
        :param language:
        :param web_api_key: `Steam Web API` key. Can be used for access `Web API`.
        :param trade_token:
        :param alias:
        """

        super().__init__(session.transport, country=country, currency=currency, language=language)

        self._session = session
        self._conf = confirmations

        self._web_api_key = web_api_key
        self._trade_token = trade_token
        self._alias = alias

        # safe defaults
        self._steam_fee = 0.5  # wallet_fee_percent
        self._publisher_fee = 0.10  # wallet_publisher_fee_percent_default
        self._fee_min = 1  # wallet_fee_minimum
        self._fee_base = 0  # wallet_fee_base

    @property
    def web_api_key(self) -> str | None:
        return self._web_api_key

    @property
    def trade_token(self) -> str | None:
        """Trade `token` of current user."""
        return self._trade_token

    @property
    def trade_url(self) -> URL | None:
        """Trade `url` of current user."""

        if self._trade_token:
            return STEAM_URL.TRADE / "new/" % {"partner": self._session.steam_id.account_id, "token": self._trade_token}

    @property
    def alias(self) -> str | None:
        """Custom `alias` of current user profile `url`, e.g `https://steamcommunity.com/id/<ALIAS>`."""
        return self._alias

    @property
    def profile_url(self) -> URL:
        """
        Profile `url` of current user.
        If ``alias`` is set, return `custom url`, e.g `https://steamcommunity.com/id/<ALIAS>`.

        .. note:: It is strongly advised to handle http redirects when this property is used.

        """

        if self._alias:
            return STEAM_URL.COMMUNITY / f"id/{self._alias}"
        else:
            return STEAM_URL.COMMUNITY / f"profiles/{self._session.steam_id.id64}"

    @property
    def steam_fee(self) -> float:
        """`Steam` fee."""
        return self._steam_fee

    @property
    def publisher_fee(self) -> float:
        """Default `publisher` fee."""
        return self._publisher_fee

    @property
    def wallet_fee_min(self) -> int:
        """Wallet `minimal` fee."""
        return self._fee_min

    @property
    def wallet_fee_base(self) -> float:
        """Wallet `base` fee."""
        return self._fee_base

    async def set_language(self, lang: Language):
        # backup option
        # POST https://store.steampowered.com/account/savelanguagepreferences json=primary_language, sessionid

        await self._transport.request(
            "POST",
            STEAM_URL.COMMUNITY / "actions/SetLanguage",
            data={"sessionid": self._session.session_id, "language": lang},
            response_mode="meta",
        )
        # We can set lang cookie to store domain, but let's follow browser behaviour
        await self._transport.request(
            "GET",
            STEAM_URL.STORE / "account/languagepreferences/",
            redirects=False,  # we don't need to load page in new language, enough first request with cookie
            response_mode="meta",
        )

    async def update_api_key(self) -> str | None:
        """
        Update `Steam Web API` key from `Steam`.

        :return: api key or ``None`` if not registered yet.
        :raises TransportError: ordinary reasons.
        :raises SteamError: unable to get api key.
        """

        r = await self._transport.request(
            "GET",
            STEAM_URL.COMMUNITY / "dev/apikey",
            params={"l": "english"},  # force english
        )
        rt: str = r.content

        if "Access Denied" in rt:
            msg = API_KEY_ERROR_RE.search(rt).group(1)
            raise SteamError(msg)

        if search := API_KEY_RE.search(rt):
            self._web_api_key = search.group(1)
        else:
            self._web_api_key = None

        return self._web_api_key

    # TODO those methods can belong to a different components
    async def revoke_api_key(self):
        """Revoke old `Steam Web API` key."""

        data = {
            "sessionid": self._session.session_id,
            "Revoke": "Revoke My Steam Web API Key",  # whatever
        }
        await self._transport.request("POST", STEAM_URL.COMMUNITY / "dev/revokekey", data=data, response_mode="meta")

        self._web_api_key = None

    async def confirm_api_key_request(self, req_id: int) -> "Confirmation":
        """Confirm `Steam Web API` key registration request."""

        if self._conf is None:
            raise ValueError("Confirmation component is required to use this method")

        conf = await self._conf.get_confirmation(req_id)
        await self._conf.allow_confirmation(conf)

        return conf

    async def register_new_api_key(self, domain: str, *, request_id: int = 0) -> str:
        """
        Request registration of a new `Steam Web API` key.

        :param domain: on which domain api key will be registered.
        :param request_id: `confirmation id` of registration request.
        :return: api key.
        :raises TransportError: ordinary reasons.
        :raises EResultError: ordinary reasons.
        :raises NeedMobileConfirmation: action requires mobile app confirmation.
        """

        await self.revoke_api_key()  # revoke old one as browser do

        data = {
            "domain": domain,
            "request_id": request_id,
            "sessionid": self._session.session_id,
            "agreeToTerms": "true",
        }
        url = STEAM_URL.COMMUNITY / "dev/requestkey"
        r = await self._transport.request("POST", url, data=data, response_mode="json")
        rj: dict = r.content

        if EResult(rj.get("success")) is EResult.PENDING and rj.get("requires_confirmation"):
            if self._conf is None:
                raise NeedMobileConfirmation(rj["request_id"])

            await self.confirm_api_key_request(rj["request_id"])

            data["request_id"] = rj["request_id"]

            r = await self._transport.request("POST", url, data=data, response_mode="json")  # repeat
            rj = r.content

        EResultError.check_data(rj)

        self._web_api_key = rj["api_key"]

        return self._web_api_key

    async def update_alias(self) -> str | None:
        """Update profile ``alias`` from `Steam`."""

        r = await self._transport.request("GET", STEAM_URL.COMMUNITY / "my", redirects=False, response_mode="meta")
        location = r.headers["Location"]
        if "profiles/" in location:  # redirect to default url so there is no alias
            self._alias = None
        else:
            self._alias = location.rsplit("/", 2)[-2]

        return self._alias

    async def update_trade_token(self) -> str | None:
        """Update ``trade_token`` from `Steam`."""

        r = await self._transport.request(
            "GET",
            self.profile_url / "tradeoffers/privacy",
            redirects=True,  # if alias is not set but existed, redirects will be handled
            response_mode="text",
        )

        search = TRADE_TOKEN_RE.search(r.content)
        self._trade_token = search.group(1) if search else None

        return self._trade_token

    async def generate_new_trade_token(self) -> str:
        """Generates new `trade url` alongside `token`. Will update ``trade_token``."""

        r = await self._transport.request(
            "POST",
            self.profile_url / "tradeoffers/newtradeurl",
            data={"sessionid": self._session.session_id},
            response_mode="json",
        )

        self._trade_token = quote(r.content, safe="~()*!.'")  # https://stackoverflow.com/a/72449666/19419998

        return self._trade_token

    # wallet method, but no better way to handle codependence :(
    async def update_wallet_info(self) -> WalletInfo:
        """Update country, currency and fees from `Steam`."""

        # get wallet info
        profile_url = self.profile_url
        r = await self._session.transport.request(
            "GET",
            profile_url / "inventory",
            headers={"Referer": str(profile_url)},
            redirects=True,  # handle redirects if profile alias unset
            response_mode="text",
        )
        rt: str = r.content
        data = json.loads(WALLET_INFO_RE.search(rt).group(1))

        EResultError.check_data(data)

        info = WalletInfo(
            Currency(data["wallet_currency"]),
            data["wallet_country"],
            data["wallet_state"],
            int(data["wallet_fee"]),
            int(data["wallet_fee_minimum"]),
            float(data["wallet_fee_percent"]),
            float(data["wallet_publisher_fee_percent_default"]),
            int(data["wallet_fee_base"]),
            int(data["wallet_balance"]),
            int(data["wallet_delayed_balance"]),
            int(data["wallet_max_balance"]),
            int(data["wallet_trade_max_balance"]),
        )

        self._currency = info.wallet_currency
        self._country = info.wallet_country
        self._steam_fee = info.wallet_fee_percent
        self._publisher_fee = info.wallet_publisher_fee_percent_default
        self._fee_min = info.wallet_fee_minimum
        self._fee_base = info.wallet_fee_base

        return info

    async def actualize(self):
        """Actualize component state for current user by updating them from `Steam`."""

        async def update_api_key():  # skip if unavailable
            with suppress(SteamError):
                await self.update_api_key()

        async with asyncio.TaskGroup() as tg:
            tg.create_task(update_api_key())
            tg.create_task(self.update_alias())
            tg.create_task(self.update_trade_token())
            tg.create_task(self.update_wallet_info())
