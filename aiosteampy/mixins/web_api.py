from re import compile
from typing import overload, Literal

from yarl import URL
from aiohttp import ClientResponseError
from aiohttp.client import _RequestContextManager

from ..constants import STEAM_URL, EResult
from ..exceptions import EResultError, SteamError, SessionExpired
from .confirmation import ConfirmationMixin

API_KEY_RE = compile(r"<p>Key: (?P<api_key>[0-9A-F]+)</p>")
STEAM_GUARD_REQ_CHECK_RE = compile(r"Your account requires (<a [^>]+>)?Steam Guard Mobile Authenticator")


class SteamWebApiMixin(ConfirmationMixin):
    """
    Contain methods related to `Steam Web API`.
    Depends on `ConfirmationMixin`.

    .. seealso:: https://steamapi.xpaw.me
    """

    __slots__ = ()

    # required instance attributes
    _api_key: str | None  # optional

    # async def web_api_get(self):
    #     pass
    #
    # async def web_api_post(self):
    #     pass

    @overload
    async def call_web_api(self, url: str | URL, params: dict = ..., use_api_key: bool = ..., headers: dict = ...):
        ...

    @overload
    async def call_web_api(
        self,
        url: str | URL,
        data: dict = ...,
        json: dict = ...,
        use_api_key: bool = ...,
        headers: dict = ...,
        *,
        method: Literal["POST"],
    ):
        ...

    async def call_web_api(
        self,
        url: str | URL,
        params={},
        data=None,
        json=None,
        use_api_key=False,
        headers: dict = None,
        *,
        method: Literal["GET", "POST"] = "GET",
    ):
        params = {**params}
        if use_api_key:
            if not self._api_key:
                raise AttributeError("You must set an `_api_key` before use this method with `use_api_key=True`")
            params["key"] = self._api_key
        else:
            params["access_token"] = self.access_token

        try:
            await self.session.request(method, url, params={**params}, data=data, json=json, headers=headers)
        except ClientResponseError as e:
            # TODO this
            if e.status == 403:
                if not use_api_key and self.is_access_token_expired:
                    raise SessionExpired from e

                raise SteamError(f"{'Steam API key' if use_api_key else 'Access token'} is invalid")
            else:
                raise e

    async def fetch_api_key(self) -> str:
        """
        Fetch `Steam Web API` key, cache it and return.

        :raises SteamError:
        """

        # https://github.com/DoctorMcKay/node-steamcommunity/blob/b58745c8b74963eae808d33e558dbba6840c7053/components/webapi.js#L18
        # force english
        r = await self.session.get(STEAM_URL.COMMUNITY / "dev/apikey", params={"l": "english"}, allow_redirects=False)
        rt = await r.text()

        if "You must have a validated email address to create a Steam Web API key" in rt:
            raise SteamError("Validated email address required to create a Steam Web API key")
        elif STEAM_GUARD_REQ_CHECK_RE.search(rt):
            # for practically impossible case when `shared_secret` is "" and mobile authenticator disabled
            raise SteamError("Steam Guard Mobile Authenticator is required")
        elif "<h2>Access Denied</h2>" in rt:
            raise SteamError("Access to Steam Web Api page is denied")

        search = API_KEY_RE.search(rt)
        if not search:
            raise SteamError("Failed to get Steam Web API key", rt)

        self._api_key = search["api_key"]
        return self._api_key

    def revoke_api_key(self) -> _RequestContextManager:
        """Revoke old `Steam Web API` key"""

        data = {
            "sessionid": self.session_id,
            "Revoke": "Revoke My Steam Web API Key",  # whatever
        }
        return self.session.post(STEAM_URL.COMMUNITY / "dev/revokekey", data=data, allow_redirects=False)

    async def register_new_api_key(self, domain: str) -> str:
        """
        Request registration of a new `Steam Web API` key, confirm, cache it and return.

        :param domain: on which domain api key will be registered
        :return: `Steam Web API` key
        :raises EResultError: for ordinary reasons
        """

        # https://github.com/DoctorMcKay/node-steamcommunity/blob/b58745c8b74963eae808d33e558dbba6840c7053/components/webapi.js#L78

        await self.revoke_api_key()  # revoke old one as website do

        data = {
            "domain": domain,
            "request_id": 0,
            "sessionid": self.session_id,
            "agreeToTerms": "true",  # or boolean True?
        }
        r = await self.session.post(STEAM_URL.COMMUNITY / "dev/requestkey", data=data)
        rj: dict[str, str | int] = await r.json()
        success = EResult(rj.get("success"))

        if success is EResult.PENDING and rj.get("requires_confirmation"):
            await self.confirm_api_key_request(rj["request_id"])
            r = await self.session.post(r.url, data=data)  # repeat
            rj: dict[str, str | int] = await r.json()
            success = EResult(rj.get("success"))

        if success is not EResult.OK or not rj["api_key"]:
            raise EResultError(rj.get("message", "Failed to register Steam Web API Key"), success, rj)

        self._api_key = rj["api_key"]
        return self._api_key
