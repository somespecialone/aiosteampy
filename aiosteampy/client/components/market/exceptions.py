from ....exceptions import SteamError


class InsufficientBalance(SteamError):
    """Wallet balance is insufficient for requested market action."""


class ListingRemoved(SteamError):
    """Listing has been removed."""
