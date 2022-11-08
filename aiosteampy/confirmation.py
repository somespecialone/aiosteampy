import enum
from typing import TYPE_CHECKING, Iterable
from json import loads
from re import compile

from bs4 import BeautifulSoup

from .models import STEAM_URL, Confirmation
from .exceptions import ApiError

if TYPE_CHECKING:
    from .client import SteamClient

INCORRECT_SG_CODES_CHECK = "Steam Guard Mobile Authenticator is providing incorrect Steam Guard codes."
CONF_URL = STEAM_URL.COMMUNITY / "mobileconf"
HTML_PARSER = "html.parser"

ITEM_INFO_RE = compile(r"'confiteminfo', (?P<item_info>.+), UserYou")


class Tag(enum.Enum):
    CONF = "conf"
    DETAILS = "details"
    ALLOW = "allow"
    CANCEL = "cancel"


class ConfirmationMixin:
    __slots__ = ()

    _confirmations: dict[int, Confirmation] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._confirmations = {}

    @property
    def confirmations(self) -> tuple[Confirmation, ...]:
        return tuple(self._confirmations.values())

    async def confirm_sell_listing(self, asset_id: int) -> dict:
        confs = await self._fetch_confirmations()
        confirmation = await self._select_sell_listing_confirmation(confs.values(), asset_id)
        return await self._send_confirmation(confirmation)

    async def _send_confirmation(self: "SteamClient", confirmation: Confirmation) -> dict:
        tag = Tag.ALLOW
        params = self._create_confirmation_params(tag.value)
        params["op"] = (tag.value,)
        params["cid"] = confirmation.data_confid
        params["ck"] = confirmation.data_key
        headers = {"X-Requested-With": "XMLHttpRequest"}
        response = await self.session.get(CONF_URL / "ajaxop", params=params, headers=headers)
        return await response.json()

    async def _fetch_confirmations(self: "SteamClient") -> dict[int, Confirmation]:
        tag = "conf"
        params = await self._create_confirmation_query_params(tag)
        headers = {"X-Requested-With": "com.valvesoftware.android.steam.community"}
        resp = await self.session.get(CONF_URL / tag, params=params, headers=headers)
        resp_text = await resp.text()
        if INCORRECT_SG_CODES_CHECK in resp_text:
            raise ApiError("Invalid Steam Guard identity secret")

        soup = BeautifulSoup(resp_text, HTML_PARSER)
        if not soup.select("#mobileconf_empty"):
            for conf_data in soup.select("#mobileconf_list .mobileconf_list_entry"):
                trade_id = int(conf_data.get("data-creator", 0))
                self._confirmations[trade_id] = Confirmation(
                    int(conf_data["id"].split("conf")[1]),
                    int(conf_data["data-confid"]),
                    int(conf_data["data-key"]),
                    trade_id,
                )

        return self._confirmations

    async def _create_confirmation_query_params(self: "SteamClient", tag: str) -> dict[str, ...]:
        conf_key, ts = await self._gen_confirmation_key(tag=tag)
        return {
            "p": self.device_id,
            "a": self.steam_id,
            "k": conf_key,
            "t": ts,
            "m": "android",
            "tag": tag,
        }

    async def _select_sell_listing_confirmation(self, confs: Iterable[Confirmation], asset_id: int) -> Confirmation:
        for conf in confs:
            await self._update_confirmation(conf)
            confirmation_id = 0
            # actually, asset id is not enough to guarantee that this is needed one item
            if confirmation_id == str(asset_id):
                return conf
        # raise ConfirmationExpected

    async def _update_confirmation(self: "SteamClient", conf: Confirmation):
        params = await self._create_confirmation_query_params(conf.tag)
        resp = await self.session.get(CONF_URL / f"details/{conf.id}", params=params)
        resp_json = await resp.json()
        text = resp_json["html"]
        data: dict[str, ...] = loads(ITEM_INFO_RE.search(text)["item_info"])
