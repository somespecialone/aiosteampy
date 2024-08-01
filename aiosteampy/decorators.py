"""Decorators for client/mixins methods"""

from typing import TYPE_CHECKING
from functools import wraps

if TYPE_CHECKING:
    from .client import SteamCommunityMixin


# without typing as PyCharm complains about return type while VsCode not
def api_key_required(f):
    @wraps(f)
    def wrapper(self: "SteamCommunityMixin", *args, **kwargs):
        if self._api_key is None:
            raise AttributeError("You must provide an API key to client or init data before use this method")
        return f(self, *args, **kwargs)

    return wrapper


def wallet_currency_required(f):
    @wraps(f)
    def wrapper(self: "SteamCommunityMixin", *args, **kwargs):
        if self._wallet_currency is None:
            raise AttributeError("You must provide wallet currency key to client or init data before use this method")
        return f(self, *args, **kwargs)

    return wrapper


def identity_secret_required(f):
    @wraps(f)
    def wrapper(self: "SteamCommunityMixin", *args, **kwargs):
        if self._identity_secret is None:
            raise AttributeError("You must provide identity secret to client before use this method")
        return f(self, *args, **kwargs)

    return wrapper
