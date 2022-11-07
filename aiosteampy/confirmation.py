from typing import TYPE_CHECKING
import enum

from bs4 import BeautifulSoup

from .models import STEAM_URL, Confirmation
from .exceptions import ApiError

if TYPE_CHECKING:
    from .client import SteamClient

INCORRECT_SG_CODES_CHECK = "Steam Guard Mobile Authenticator is providing incorrect Steam Guard codes."
CONF_URL = STEAM_URL.COMMUNITY / "mobileconf"
HTML_PARSER = "html.parser"


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

    async def send_trade_allow_request(self, trade_offer_id: str) -> dict:
        confirmations = await self._fetch_confirmations()
        # TODO find how to determine which confirmation belongs to which order
        confirmation = await self._select_trade_offer_confirmation(confirmations, trade_offer_id)
        return await self._send_confirmation(confirmation)

    async def confirm_sell_listing(self, asset_id: int) -> dict:
        confs = await self._fetch_confirmations()
        confirmation = await self._select_sell_listing_confirmation(confs, asset_id)
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
                pass

        return self._confirmations

    async def _fetch_confirmation_details_page(self: "SteamClient", confirmation: Confirmation) -> str:
        params = await self._create_confirmation_query_params("details" + confirmation.id)
        resp = await self.session.get(CONF_URL / f"details/{confirmation.id}", params=params)
        resp_json = await resp.json()
        return resp_json["html"]

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

    async def _select_trade_offer_confirmation(
        self, confirmations: list[Confirmation], trade_offer_id: str
    ) -> Confirmation:
        for confirmation in confirmations:
            confirmation_details_page = await self._fetch_confirmation_details_page(confirmation)
            confirmation_id = self._get_confirmation_trade_offer_id(confirmation_details_page)
            if confirmation_id == trade_offer_id:
                return confirmation
        # raise ConfirmationExpected

    async def _select_sell_listing_confirmation(self, confirmations: list[Confirmation], asset_id: int) -> Confirmation:
        for confirmation in confirmations:
            confirmation_details_page = await self._fetch_confirmation_details_page(confirmation)
            confirmation_id = self._get_confirmation_sell_listing_id(confirmation_details_page)
            if confirmation_id == str(asset_id):
                return confirmation
        # raise ConfirmationExpected

    @staticmethod
    def _get_confirmation_sell_listing_id(confirmation_details_page: str) -> str:
        soup = BeautifulSoup(confirmation_details_page, "")
        scr_raw = soup.select("script")[2].string.strip()
        scr_raw = scr_raw[scr_raw.index("'confiteminfo', ") + 16 :]
        scr_raw = scr_raw[: scr_raw.index(", UserYou")].replace("\n", "")
        # return json.loads(scr_raw)["id"]

    @staticmethod
    def _get_confirmation_trade_offer_id(confirmation_details_page: str) -> str:
        soup = BeautifulSoup(confirmation_details_page, "")
        full_offer_id = soup.select(".tradeoffer")[0]["id"]
        return full_offer_id.split("_")[1]
