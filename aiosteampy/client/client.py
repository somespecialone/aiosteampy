import asyncio
from typing import TYPE_CHECKING, Self

from ..constants import LIB_ID, EResult, Platform, SteamURL
from ..exceptions import EResultError, MobileConfirmationRequired, Unauthenticated
from ..session import SteamSession
from ..transport import BaseSteamTransport, Cookie, DefaultSteamTransport
from ..webapi import SteamWebAPIClient
from .components.inventory import InventoryComponent, InventoryPublicComponent
from .components.market import MarketComponent, MarketPublicComponent
from .components.notifications import NotificationsComponent
from .components.profile import ProfileComponent, ProfilePublicComponent
from .components.trade import TradeComponent
from .components.wallet import WalletComponent
from .constants import Currency, Language
from .state import (
    DEF_COUNTRY,
    DEF_CURRENCY,
    DEF_FEE_BASE,
    DEF_FEE_MIN,
    DEF_LANGUAGE,
    DEF_PUBLISHER_FEE,
    DEF_STEAM_FEE,
    PublicSteamState,
    SteamState,
)

if TYPE_CHECKING:  # optional import
    from ..guard import SteamConfirmations, TwoFactorSigner


LANG_COOKIE = "Steam_Language"


def set_language_cookie(transport: BaseSteamTransport, lang: Language):
    for domain in SteamURL.DOMAINS:
        transport.add_cookie(
            Cookie(
                LANG_COOKIE,
                lang.value,
                domain.host,
                domain.path,
            )
        )


class SteamPublicClient:
    __slots__ = ("_state", "_market", "_profile", "_inventory")

    def __init__(
        self,
        *,
        transport: BaseSteamTransport | None = None,
        proxy: str | None = None,
        platform: Platform = Platform.WEB,  # let it be
        # state
        country: str = DEF_COUNTRY,
        currency: Currency = DEF_CURRENCY,
        language: Language = DEF_LANGUAGE,
    ):
        """
        Abstract container for `Steam` domains interaction
        from a *non-authenticated user* perspective.

        :param transport: A custom transport instance implementing the required
            HTTP communication interface. If provided, ``proxy`` cannot also be set.
        :param proxy: A proxy URL to route HTTP requests through when using the *default HTTP transport*.
        :param platform: The platform type for which the client is being initialized.
        :param country: 2-letter country code.
        :param currency: currency of requested data.
        :param language: language of `Steam` responses, descriptions, et cetera.
        """

        if transport is not None and proxy is not None:
            raise ValueError("Proxy is not supported for custom transport")

        transport = transport or DefaultSteamTransport(proxy=proxy, ctx={"platform": platform, "user_agent": LIB_ID})

        self._state = PublicSteamState(transport, country=country, currency=currency, language=language)
        self._market = MarketPublicComponent(transport, self._state)
        self._profile = ProfilePublicComponent(transport)
        self._inventory = InventoryPublicComponent(transport, self._state)

        set_language_cookie(transport, language)

    @property
    def language(self) -> Language:
        """Language of `Steam` responses, descriptions, et cetera."""
        return self._state.language

    @property
    def transport(self) -> BaseSteamTransport:
        """HTTP transport instance."""
        return self._state._transport

    @property
    def state(self) -> PublicSteamState:
        """Non-authenticated user state."""
        return self._state

    @property
    def market(self) -> MarketPublicComponent:
        """`Steam Market`."""
        return self._market

    @property
    def profile(self) -> ProfilePublicComponent:
        """Profile domain public methods."""
        return self._profile

    @property
    def inventory(self) -> InventoryPublicComponent:
        """Users inventory interaction."""
        return self._inventory

    def set_language(self, lang: Language):
        """
        Set main `language` of `Steam` domains.

        Language other than `English` can **break methods and lead to unexpected behavior**.
        """

        # browser behavior:
        # POST https://store.steampowered.com/account/setlanguage/ json={language, sessionid}
        # POST https://steamcommunity.com/actions/SetLanguage/ json={language, sessionid}
        # all work from above just to set cookies, so we can bypass requests and set it manually

        set_language_cookie(self.transport, lang)
        self._state._language = lang

    def __repr__(self):
        return f"{self.__class__.__name__}(currency={self._state.currency.name}, country={self._state.country})"

    def serialize(self) -> dict:
        """Serialize current `Client` state to `JSON-safe` dict."""
        return {"state": self._state.serialize(), "cookies": self.transport.get_serialized_cookies()}

    @classmethod
    def deserialize(
        cls,
        serialized: dict,
        transport: BaseSteamTransport | None = None,
        proxy: str | None = None,
    ) -> Self:
        """Deserialize `Client` from previously ``serialized`` data."""

        client = cls(transport=transport, proxy=proxy, **serialized["state"])
        client.transport.update_serialized_cookies(serialized["cookies"])
        return client


class SteamClient:
    __slots__ = (
        "_session",
        "_conf",
        "_state",
        "_market",
        "_profile",
        "_inventory",
        "_trade",
        "_wallet",
        "_notifications",
    )

    def __init__(
        self,
        session: SteamSession,
        *,
        # guard/confirmations
        shared_secret: str | bytes | None = None,
        identity_secret: str | bytes | None = None,
        device_id: str | None = None,
        time_offset: int | None = None,
        # state
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
        _ignore_invalid: bool = False,
    ):
        """
        Abstract container for `Steam` domains interaction
        from *authenticated user* perspective.

        :param session: authenticated session.
        :param shared_secret: shared secret of an account in bytes or base64 encoded string.
        :param identity_secret: identity secret of an account in bytes or base64 encoded string.
        :param device_id: generated device id.
        :param time_offset: known offset in seconds from server time.
        :param country: 2-letter country code.
        :param currency: currency of requested data.
        :param language: language of `Steam` responses, descriptions, et cetera.
        :param web_api_key: `Steam Web API` key. Can be used for access `Web API`.
        :param trade_token: trade `token` from account trade url.
        :param alias: custom profile `alias`.
        :param steam_fee: wallet fee percent.
        :param publisher_fee: wallet `publisher` fee percent.
        :param fee_min: wallet `fee` minimum.
        :param fee_base: wallet `base` fee.
        """

        self._session = session

        if not _ignore_invalid and not session.cookies_are_valid:
            raise Unauthenticated
        if (not shared_secret and identity_secret) or (shared_secret and not identity_secret):
            raise ValueError("Both shared and identity secrets must be provided")

        self._conf = None
        if shared_secret:
            from ..guard import SteamConfirmations, TwoFactorSigner

            signer = TwoFactorSigner(
                self._session.steam_id,
                shared_secret=shared_secret,
                identity_secret=identity_secret,
                webapi=self._session.webapi,
                time_offset=time_offset,
            )
            self._conf = SteamConfirmations(self._session, signer, device_id)

        self._state = SteamState(
            self._session,
            country=country,
            currency=currency,
            language=language,
            web_api_key=web_api_key,
            trade_token=trade_token,
            alias=alias,
            steam_fee=steam_fee,
            publisher_fee=publisher_fee,
            fee_min=fee_min,
            fee_base=fee_base,
        )
        self._market = MarketComponent(self._session, self._state, self._conf)
        self._profile = ProfileComponent(self._session, self._state)
        self._inventory = InventoryComponent(self._session, self._state)
        self._trade = TradeComponent(self._session, self._state, self._conf)
        self._wallet = WalletComponent(self._session, self._state)
        self._notifications = NotificationsComponent(self._session)

        set_language_cookie(session.transport, language)

    @property
    def language(self) -> Language:
        """Language of `Steam` responses, descriptions, et cetera."""
        return self._state.language

    @property
    def transport(self) -> BaseSteamTransport:
        """HTTP transport instance."""
        return self._session.transport

    @property
    def session(self) -> SteamSession:
        """Authenticated `Steam` session."""
        return self._session

    @property
    def confirmations(self) -> "SteamConfirmations | None":
        """`Steam` mobile confirmations manager."""
        return self._conf

    @property
    def state(self) -> SteamState:
        """Authenticated user state instance."""
        return self._state

    @property
    def market(self) -> MarketComponent:
        """`Steam Market`."""
        return self._market

    @property
    def profile(self) -> ProfileComponent:
        """Profile-related functionality."""
        return self._profile

    @property
    def inventory(self) -> InventoryComponent:
        """Inventory interaction."""
        return self._inventory

    @property
    def trade(self) -> TradeComponent:
        """Trade-related actions."""
        return self._trade

    @property
    def wallet(self) -> WalletComponent:
        """User wallet-related actions."""
        return self._wallet

    @property
    def notifications(self) -> NotificationsComponent:
        """User notifications."""
        return self._notifications

    @property
    def webapi(self) -> SteamWebAPIClient:
        """`Steam Web API` client."""
        return self._session.webapi

    async def set_language(self, lang: Language):
        """
        Set main `language` of `Steam` domains.

        Language other than `English` can **break methods and lead to unexpected behavior**.
        """

        # backup option
        # POST https://store.steampowered.com/account/savelanguagepreferences json={primary_language, sessionid}

        await self._session.transport.request(
            "POST",
            SteamURL.COMMUNITY / "actions/SetLanguage",
            data={"sessionid": self._session.session_id, "language": lang},
            response_mode="meta",
        )
        # We can set lang cookie to store domain, but let's follow browser behavior
        await self._session.transport.request(
            "GET",
            SteamURL.STORE / "account/languagepreferences/",
            redirects=False,  # we don't need to load page in new language, enough first response with cookie
            response_mode="meta",
        )

        self._state._language = lang

    async def revoke_api_key(self):
        """Revoke old `Steam Web API` key."""

        data = {
            "sessionid": self._session.session_id,
            "Revoke": "Revoke My Steam Web API Key",  # whatever
        }
        await self._session.transport.request(
            "POST",
            SteamURL.COMMUNITY / "dev/revokekey",
            data=data,
            response_mode="meta",
        )

        self._state._web_api_key = None

    async def register_new_api_key(self, domain: str, *, request_id: int = 0) -> str:
        """
        Request registration of a new `Steam Web API` key.

        :param domain: on which domain api key will be registered.
        :param request_id: `confirmation id` of registration request.
        :raises TransportError: ordinary reasons.
        :raises EResultError: ordinary reasons.
        :raises MobileConfirmationRequired: action requires mobile app confirmation.
        """

        if not request_id:
            await self.revoke_api_key()  # revoke old one as browser do

        data = {
            "domain": domain,
            "request_id": request_id,
            "sessionid": self._session.session_id,
            "agreeToTerms": "true",
        }
        url = SteamURL.COMMUNITY / "dev/requestkey"
        r = await self._session.transport.request("POST", url, data=data, response_mode="json")
        rj: dict = r.content

        if EResult(rj.get("success")) is EResult.PENDING and rj.get("requires_confirmation"):
            if self._conf is None:
                raise MobileConfirmationRequired(rj["request_id"])

            await self._conf.confirm_api_key_request(rj["request_id"])
            return await self.register_new_api_key(domain, request_id=rj["request_id"])

        EResultError.check_data(rj)
        self._state._web_api_key = rj["api_key"]
        return self._state.web_api_key

    async def setup(self):
        """
        Setup **new** user account which includes:

        - ``profile`` setup;
        - making ``profile`` public;
        - set ``language`` to `English`;
        - acknowledge trade rules.
        """

        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._profile.setup())  # can be made safely alongside other profile actions
            tg.create_task(self._profile.make_public())
            tg.create_task(self.set_language(Language.ENGLISH))
            tg.create_task(self._trade.acknowledge_rules())

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({self._session.steam_id}/{self._session.account_name}, "
            f"{self._session.platform})"
        )

    def serialize(self) -> dict:
        """Serialize current `Client` state to `JSON-safe` dict."""

        data = {"state": self._state.serialize(), "session": self._session.serialize()}
        if self._conf:
            data["guard"] = {
                "shared_secret": self._conf.signer.shared_secret.serialize(),
                "identity_secret": self._conf.signer.identity_secret.serialize(),
                "device_id": self._conf.device_id,
            }

        return data

    @classmethod
    def deserialize(
        cls,
        serialized: dict,
        transport: BaseSteamTransport | None = None,
        proxy: str | None = None,
    ) -> Self:
        """Deserialize `Client` from previously ``serialized`` data."""

        data = {
            "session": SteamSession.deserialize(serialized["session"], transport, proxy),
            **serialized.get("guard", {}),
            **serialized["state"],
            "language": Language(serialized["state"]["language"]),
            "currency": Currency(serialized["state"]["currency"]),
        }
        return cls(**data, _ignore_invalid=True)
