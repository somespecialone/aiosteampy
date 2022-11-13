from aiohttp import ClientSession

from .models import STEAM_URL, Currency
from .public_models import ItemOrdersHistogram
from .exceptions import ApiError


# TODO fetch listings history (check steammarket page)
#  orders activity https://steamcommunity.com/market/itemordersactivity?country=RU&language=ukrainian&currency=5&item_nameid=176321160&two_factor=0
#  get user inventory
class SteamPublicMixin:
    """Mixin contain methods that do not need authorization."""

    __slots__ = ()

    session: ClientSession
    language: str
    currency: Currency
    country: str

    async def fetch_item_orders_histogram(
        self,
        item_nameid: int,
        *,
        lang: str = None,
        country: str = None,
        currency: Currency = None,
    ) -> ItemOrdersHistogram:
        """
        Do what described in method name.

        `Warning!` - steam rate limit this request.

        https://github.com/somespecialone/steam-item-name-ids

        :param item_nameid: special id of item class. Can be found only on listings page.
        :param lang:
        :param country:
        :param currency:
        :return: `ItemOrdersHistogram` dict
        :raises ApiError:
        """

        params = {
            "norender": 1,
            "language": lang or self.language,
            "country": country or self.country,
            "currency": currency.value if currency else self.currency.value,
            "item_nameid": item_nameid,
        }
        r = await self.session.get(STEAM_URL.MARKET / "itemordershistogram", params=params)
        rj: ItemOrdersHistogram = await r.json()
        if not rj.get("success"):
            raise ApiError("Can't fetch item orders histogram.", rj)

        return rj
