from ....exceptions import SteamError


class MarketError(SteamError):
    """Generic error for market related activities."""


class InsufficientBalance(MarketError):
    """Wallet balance is insufficient for requested market action."""


class ListingRemoved(MarketError):
    """Listing has been removed."""
