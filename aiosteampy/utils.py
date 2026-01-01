"""Abstract utils within `Steam` context and not"""

import asyncio

from base64 import b64decode, b64encode
from datetime import datetime
from struct import pack, unpack
from time import time as time_time
from hmac import new as hmac_new
from hashlib import sha1
from functools import wraps, partial
from typing import Callable, overload, TypeVar, TypeAlias, Literal
from http.cookies import SimpleCookie, Morsel
from math import floor
from secrets import token_hex
from re import search as re_search, compile as re_compile
from json import loads as j_loads

from yarl import URL

from .typed import JWTToken


__all__ = (
    "extract_openid_payload",
    "async_throttle",
    "create_ident_code",
    "make_inspect_link",
)


def extract_openid_payload(page_text: str) -> dict[str, str]:
    """
    Extract steam openid urlencoded (specs) from page html raw text.
    Use it if 3rd party websites have extra or non-cookie auth (JWT via service API call, for ex.).

    :param page_text:
    :return: dict with urlencoded data
    """

    # not so beautiful as with bs4 but dependency free
    return {
        "action": re_search(r"id=\"actionInput\"[\w=\"\s]+value=\"(?P<action>\w+)\"", page_text)["action"],
        "openid.mode": re_search(r"name=\"openid\.mode\"[\w=\"\s]+value=\"(?P<mode>\w+)\"", page_text)["mode"],
        "openidparams": re_search(r"name=\"openidparams\"[\w=\"\s]+value=\"(?P<params>[\w=/]+)\"", page_text)["params"],
        "nonce": re_search(r"name=\"nonce\"[\w=\"\s]+value=\"(?P<nonce>\w+)\"", page_text)["nonce"],
    }


_R = TypeVar("_R")


def async_throttle(
    seconds: float,
    *,
    arg_index: int | None = None,
    arg_name: str | None = None,
) -> Callable[[Callable[..., _R]], Callable[..., _R]]:
    """
    Prevents the decorated function from being called more than once per ``seconds``.
    Throttle (`await asyncio.sleep`) before call wrapped async func,
    when related arg was equal (same hash value) to related arg passed in previous func call
    if time between previous and current call lower than ``seconds``.
    Related arg must be *hashable* (can be dict key).
    Wrapped func must be *async* (return ``Coroutine``).
    Throttle every func call time if related arg has been not specified.

    :param seconds: seconds during which call frequency has been limited.
    :param arg_index: index of related arg in ``*args`` tuple.
    :param arg_name: keyname of related arg in ``**kwargs`` dict.
    """

    if arg_index is not None and arg_name is not None:
        raise ValueError("You can't specify both `arg_index` and `arg_name`")

    # mega optimization, prevent arg checks in wrapped func call
    # I know about PEP8: E731, but this way is much shorter and readable
    if arg_index is None and arg_name is None:
        get_key = lambda _, __: None
    elif arg_index:
        get_key = lambda a, _: a[arg_index]
    else:
        get_key = lambda _, k: k[arg_name]

    ts_map: dict[..., float] = {}

    def decorator(f: Callable[..., _R]) -> Callable[..., _R]:
        @wraps(f)
        async def wrapper(*args, **kwargs) -> _R:
            key = get_key(args, kwargs)
            ts = time_time()
            diff = ts - ts_map.get(key, 0)
            if diff < seconds:
                await asyncio.sleep(diff + 0.01)  # +10ms to ensure that second passed since last call
                ts_map[key] = time_time()
            else:
                ts_map[key] = ts

            return await f(*args, **kwargs)

        return wrapper

    return decorator


# TODO remove overloading and write examples in docstring: args should be from most narrow to wide (inst, class, app)
@overload
def create_ident_code(asset_id: int | str, context_id: int | str, app_id: int | str, *, sep: str = ...) -> str: ...


@overload
def create_ident_code(instance_id: int | str, class_id: int | str, app_id: int | str, *, sep: str = ...) -> str: ...


def create_ident_code(*args, sep=":"):
    """
    Create unique ident code for ``EconItem`` or ``ItemDescription`` within whole `Steam Economy`.

    .. seealso:: https://dev.doctormckay.com/topic/332-identifying-steam-items/
    """

    return sep.join(reversed(list(str(i) for i in filter(lambda i: i is not None, args))))


@overload
def make_inspect_link(*, owner_id: int, asset_id: int, d_id: int) -> str: ...


@overload
def make_inspect_link(*, market_id: int, asset_id: int, d_id: int) -> str: ...


def make_inspect_link(*, market_id: int = None, owner_id: int = None, asset_id: int, d_id: int) -> str:
    """Create `Inspect in game` link for `CS2` item."""

    base = "steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20"
    if market_id:
        return f"{base}M{market_id}A{asset_id}D{d_id}"
    else:
        return f"{base}S{owner_id}A{asset_id}D{d_id}"
