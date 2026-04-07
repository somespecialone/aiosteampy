"""State shared between components."""

import asyncio
import json
import re
from contextlib import suppress
from typing import NamedTuple, Self

from yarl import URL

from ..constants import STEAM_URL, Currency, Language
from ..exceptions import EResultError, SteamError
from ..session import SteamSession
from ..transport import BaseSteamTransport
from ._base import BasePublicComponent

TRADE_TOKEN_RE = re.compile(r"\d+&token=(.+)\" readonly")

API_KEY_RE = re.compile(r"<p>Key: ([0-9A-F]+)</p>")
API_KEY_ERROR_RE = re.compile(r"<div id=\"bodyContents_lo\">\s+?<p>(.+)</p>")

WALLET_INFO_RE = re.compile(r"g_rgWalletInfo = (.+);")


DEF_COUNTRY = "UA"
DEF_CURRENCY = Currency.USD
DEF_LANGUAGE = Language.ENGLISH


# single source of truth. Must contain only sync logic
class PublicSteamState(BasePublicComponent):
    __slots__ = ("_country", "_currency", "_language")

    def __init__(
        self,
        transport: BaseSteamTransport,
        *,
        country: str = DEF_COUNTRY,
        currency: Currency = DEF_CURRENCY,
        language: Language = DEF_LANGUAGE,
    ):
        """
        Handle state of non-authenticated user, therefore
        does not require `Steam` session.

        :param transport: transport to use.
        :param country: 2-letter country code.
        :param currency: currency of requested data.
        :param language: language of `Steam` responses, descriptions, et cetera.
        """

        super().__init__(transport)

        self._country = country
        self._currency = currency

        self._language = language

    @property
    def country(self) -> str:
        """2-letter country code of data requested from `Steam`."""
        return self._country

    @property
    def currency(self) -> Currency:
        """Currency of data requested from `Steam`."""
        return self._currency

    @property
    def language(self) -> Language:
        """Language of `Steam` responses, descriptions, et cetera."""
        return self._language

    def serialize(self) -> dict:
        """Serialize the inner state to a `JSON-safe` dict."""
        return {"country": self._country, "currency": self._currency, "language": self._language}


class WalletInfo(NamedTuple):
    """Wallet information of the current user."""

    currency: Currency
    """Wallet currency."""
    country: str
    """Account and wallet country."""
    state: str
    """Wallet state."""
    fee: int
    """Wallet fee."""
    fee_minimum: int
    """Wallet minimal fee."""
    steam_fee: float  # fee percent
    publisher_fee: float  # publisher_fee_percent_default
    """Default `publisher` fee percent."""
    market_minimum: int
    """Wallet market minimum."""
    currency_increment: int
    """Wallet currency increment."""
    fee_base: int
    """Wallet base fee."""
    balance: int
    """Wallet balance."""
    delayed_balance: int
    max_balance: int
    """Wallet max. balance."""
    trade_max_balance: int

    @classmethod
    def from_data(cls, data: dict) -> Self:
        return cls(
            currency=Currency(data["wallet_currency"]),
            country=data["wallet_country"],
            state=data["wallet_state"],
            fee=int(data["wallet_fee"]),
            fee_minimum=int(data["wallet_fee_minimum"]),
            steam_fee=float(data["wallet_fee_percent"]),
            publisher_fee=float(data["wallet_publisher_fee_percent_default"]),
            market_minimum=int(data["wallet_market_minimum"]),
            currency_increment=int(data["wallet_currency_increment"]),
            fee_base=int(data["wallet_fee_base"]),
            balance=int(data["wallet_balance"]),
            delayed_balance=int(data["wallet_delayed_balance"]),
            max_balance=int(data["wallet_max_balance"]),
            trade_max_balance=int(data["wallet_trade_max_balance"]),
        )


DEF_STEAM_FEE = 0.5
DEF_PUBLISHER_FEE = 0.10
DEF_FEE_MIN = 1
DEF_FEE_BASE = 0


class SteamState(PublicSteamState):
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
        *,
        country: str = DEF_COUNTRY,
        currency: Currency = DEF_CURRENCY,
        language: Language = DEF_LANGUAGE,
        web_api_key: str | None = None,
        trade_token: str | None = None,
        alias: str | None = None,
        steam_fee: float = DEF_STEAM_FEE,
        publisher_fee: float = DEF_PUBLISHER_FEE,
        fee_min: int = DEF_FEE_MIN,
        fee_base: int = DEF_FEE_BASE,
    ):
        """
        Handle state of authenticated user.

        :param session: authenticated session.
        :param country: 2-letter country code.
        :param currency: currency of requested data.
        :param language: language of `Steam` responses, descriptions, et cetera.
        :param web_api_key: `Steam Web API` key. Can be used for access `Web API`.
        :param trade_token: trade `token` from account trade url.
        :param alias: custom profile `alias`.
        """

        super().__init__(session.transport, country=country, currency=currency, language=language)

        self._session = session

        self._web_api_key = web_api_key
        self._trade_token = trade_token
        self._alias = alias

        # safe defaults
        self._steam_fee = steam_fee  # wallet_fee_percent
        self._publisher_fee = publisher_fee  # wallet_publisher_fee_percent_default
        self._fee_min = fee_min  # wallet_fee_minimum
        self._fee_base = fee_base  # wallet_fee_base

    @property
    def web_api_key(self) -> str | None:
        return self._web_api_key

    @property
    def trade_token(self) -> str | None:
        """Trade `token` of current user."""
        return self._trade_token

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
            return STEAM_URL.COMMUNITY / f"profiles/{self._session.steam_id}"

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

    async def sync_api_key(self) -> str | None:
        """
        Update `Steam Web API` key from `Steam`.

        :return: api key or ``None`` if not registered.
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

    async def sync_alias(self) -> str | None:
        """Update profile ``alias`` from `Steam`."""

        r = await self._transport.request("GET", STEAM_URL.COMMUNITY / "my", redirects=False, response_mode="meta")
        location = r.headers["Location"]
        if "profiles/" in location:  # redirect to default url so there is no alias
            self._alias = None
        else:
            self._alias = location.rsplit("/", 2)[-2]

        return self._alias

    async def sync_trade_token(self) -> str | None:
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

    # wallet method, but no better way to handle codependence :(
    async def sync_wallet_info(self) -> WalletInfo:
        """Update country, currency, and fees from `Steam`."""

        # get wallet info
        profile_url = self.profile_url
        r = await self._transport.request(
            "GET",
            profile_url / "inventory",
            headers={"Referer": str(profile_url)},
            redirects=True,  # handle redirects if profile alias unset
            response_mode="text",
        )
        rt: str = r.content
        data = json.loads(WALLET_INFO_RE.search(rt).group(1))

        EResultError.check_data(data)

        info = WalletInfo.from_data(data)

        self._currency = info.currency
        self._country = info.country
        self._steam_fee = info.steam_fee
        self._publisher_fee = info.publisher_fee
        self._fee_min = info.fee_minimum
        self._fee_base = info.fee_base

        return info

    async def actualize(self):
        """Actualize component state for current user by updating it from `Steam`."""

        async def sync_api_key():  # skip if unavailable
            with suppress(SteamError):
                await self.sync_api_key()

        async with asyncio.TaskGroup() as tg:
            tg.create_task(sync_api_key())
            tg.create_task(self.sync_alias())
            tg.create_task(self.sync_trade_token())
            tg.create_task(self.sync_wallet_info())

    def serialize(self) -> dict:
        return {
            **super().serialize(),
            "web_api_key": self._web_api_key,
            "trade_token": self._trade_token,
            "alias": self._alias,
            "steam_fee": self._steam_fee,
            "publisher_fee": self._publisher_fee,
            "fee_min": self._fee_min,
            "fee_base": self._fee_base,
        }
