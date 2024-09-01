from re import compile
from typing import overload, Literal

from yarl import URL
from aiohttp import ClientResponseError

from ..constants import STEAM_URL, EResult, T_PARAMS, T_HEADERS
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

    @overload
    async def call_web_api(
        self,
        url: str | URL,
        *,
        params: T_PARAMS = ...,
        use_api_key: bool = ...,
        headers: T_HEADERS = ...,
    ) -> dict[str, ...]:
        ...

    @overload
    async def call_web_api(
        self,
        url: str | URL,
        *,
        data=...,
        use_api_key: bool = ...,
        headers: T_HEADERS = ...,
        method: Literal["POST"],
    ) -> dict[str, ...]:
        ...

    @overload
    async def call_web_api(
        self,
        url: str | URL,
        *,
        json=...,
        use_api_key: bool = ...,
        headers: T_HEADERS = ...,
        method: Literal["POST"],
    ) -> dict[str, ...]:
        ...

    # https://github.com/DoctorMcKay/node-steam-tradeoffer-manager/blob/7d27ae16642ad810a44d1aed7837872b92392daf/lib/webapi.js#L7
    async def call_web_api(
        self,
        url: str | URL,
        *,
        params={},
        data=None,
        json=None,
        use_api_key=False,
        headers: T_HEADERS = None,
        method: Literal["GET", "POST"] = "GET",
    ) -> dict[str, ...]:
        """
        Make request to a `Steam Web API`

        :param url:
        :param params: params to pass with url
        :param data: form data to send with request
        :param json: json data to send with request
        :param use_api_key: force to use `Steam Web API` key instead of access token
        :param headers:
        :param method: http request method
        :return: json-loaded data
        :raises SessionExpired:
        :raises SteamError:
        """

        params = params.copy()
        if use_api_key:
            if not self._api_key:
                raise AttributeError("You must set an `_api_key` before use this method with `use_api_key=True`")
            params["key"] = self._api_key
        else:
            params["access_token"] = self.access_token

        try:
            r = await self.session.request(method, url, params=params, data=data, json=json, headers=headers)
        except ClientResponseError as e:
            if e.status == 403:
                if not use_api_key and self.is_access_token_expired:
                    raise SessionExpired from e
                else:
                    raise SteamError(f"{'Steam Web API key' if use_api_key else 'Access token'} is invalid") from e
            else:
                raise e

        # https://github.com/DoctorMcKay/node-steam-tradeoffer-manager/blob/7d27ae16642ad810a44d1aed7837872b92392daf/lib/webapi.js#L56
        result = EResult(int(r.headers["X-Eresult"]))
        if r.content.total_bytes > 0:
            rj: dict = await r.json()
            if len(rj) > 1 or len(rj.get("response", ())) > 0:
                return rj

        elif result is not EResult.OK:
            raise EResultError(f"Failed to make {method} request to '{url}'", result)
        else:
            raise SteamError("Invalid response")

    async def get_api_key(self) -> str:
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

    async def revoke_api_key(self):
        """Revoke old `Steam Web API` key"""

        data = {
            "sessionid": self.session_id,
            "Revoke": "Revoke My Steam Web API Key",  # whatever
        }
        await self.session.post(STEAM_URL.COMMUNITY / "dev/revokekey", data=data, allow_redirects=False)
        self._api_key = None

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
