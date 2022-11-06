from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import SteamClient

    JustForTypeHints = SteamClient
else:
    JustForTypeHints = object


class MarketMixin(JustForTypeHints):
    __slots__ = ()

    def buy(self):
        self
