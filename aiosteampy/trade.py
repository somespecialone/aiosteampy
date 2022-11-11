from urllib.parse import quote

from yarl import URL

from .models import STEAM_URL


class TradeMixin:
    """
    Mixin with tradeoffers related methods.
    """

    __slots__ = ()
