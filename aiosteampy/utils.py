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
    "gen_auth_code",
    "generate_confirmation_key",
    "generate_device_id",
    "extract_openid_payload",
    "async_throttle",
    "create_ident_code",
    "account_id_to_steam_id",
    "steam_id_to_account_id",
    "id64_to_id32",
    "id32_to_id64",
    "to_int_boolean",
    "buyer_pays_to_receive",
    "receive_to_buyer_pays",
    "generate_session_id",
    "decode_jwt",
    "find_item_name_id_in_text",
    "parse_time",
    "format_time",
    "make_inspect_link",
    "calc_market_listing_fee",
)


def gen_auth_code(shared_secret: str, timestamp: int = None) -> str:
    """Generate two-factor (one-time/TOTP) auth code."""

    if timestamp is None:
        timestamp = int(time_time())
    time_buffer = pack(">Q", timestamp // 30)  # pack as Big endian, uint64
    time_hmac = hmac_new(b64decode(shared_secret), time_buffer, digestmod=sha1).digest()
    begin = ord(time_hmac[19:20]) & 0xF
    full_code = unpack(">I", time_hmac[begin : begin + 4])[0] & 0x7FFFFFFF  # unpack as Big endian uint32
    chars = "23456789BCDFGHJKMNPQRTVWXY"
    code = ""

    for _ in range(5):
        full_code, i = divmod(full_code, len(chars))
        code += chars[i]

    return code


def generate_confirmation_key(identity_secret: str, tag: str, timestamp: int | None = None) -> str:
    """Generate confirmation key."""

    timestamp = int(time_time()) if timestamp is None else timestamp
    buff = pack(">Q", timestamp) + tag.encode("ascii")
    return b64encode(hmac_new(b64decode(identity_secret), buff, digestmod=sha1).digest()).decode()


# It works, however it's different that one generated from mobile app
def generate_device_id(steam_id64: int) -> str:
    """
    Generate mobile android device id.
    :param steam_id64: 64bit representation of `Steam ID`
    """

    hexed_steam_id = sha1(str(steam_id64).encode("ascii")).hexdigest()
    return "android:" + "-".join(
        [hexed_steam_id[:8], hexed_steam_id[8:12], hexed_steam_id[12:16], hexed_steam_id[16:20], hexed_steam_id[20:32]]
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


def steam_id_to_account_id(steam_id: int) -> int:
    """Convert steam id64 to steam id32."""

    return steam_id & 0xFFFFFFFF


def account_id_to_steam_id(account_id: int) -> int:
    """Convert steam id32 to steam id64."""

    return 1 << 56 | 1 << 52 | 1 << 32 | account_id


# aliases
id64_to_id32 = steam_id_to_account_id
id32_to_id64 = account_id_to_steam_id


def to_int_boolean(s):
    """Convert something to 1, 0."""

    return 1 if s else 0


JSONABLE_COOKIE_JAR = list[dict[str, dict[str, str | None | bool]]]


# TODO this
from aiohttp import ClientSession


def update_session_cookies(session: ClientSession, cookies: JSONABLE_COOKIE_JAR):
    """Update the session cookies from jsonable cookie jar."""

    for cookie_data in cookies:
        c = SimpleCookie()
        for k, v in cookie_data.items():
            copied = dict(**v)  # copy to avoid modification of the arg
            m = Morsel()
            m._value = copied.pop("value")
            m._key = copied.pop("key")
            m._coded_value = copied.pop("coded_value")
            m.update(copied)
            c[k] = m

        session.cookie_jar.update_cookies(c)


# def get_jsonable_cookies(session: ClientSession) -> JSONABLE_COOKIE_JAR:
#     """Extract and convert cookies to dict object."""
#
#     return [
#         {
#             field_key: {
#                 "coded_value": morsel.coded_value,
#                 "key": morsel.key,
#                 "value": morsel.value,
#                 "expires": morsel["expires"],
#                 "path": morsel["path"],
#                 "comment": morsel["comment"],
#                 "domain": morsel["domain"],
#                 "max-age": morsel["max-age"],
#                 "secure": morsel["secure"],
#                 "httponly": morsel["httponly"],
#                 "version": morsel["version"],
#                 "samesite": morsel["samesite"],
#             }
#             for field_key, morsel in cookie.items()
#         }
#         for cookie in session.cookie_jar._cookies.values()
#         if cookie  # skip empty cookies
#     ]


def receive_to_buyer_pays(
    amount: int,
    *,
    publisher_fee: float = 0.10,
    steam_fee: float = 0.05,
    wallet_fee_min: float = 1,
    wallet_fee_base: float = 0,
) -> tuple[int, int, int]:
    """
    Convert `to_receive` amount to `buyer_pays`. Mostly needed for placing sell listing.
    Works just like function from sell listing window on `Steam`.

    :param amount: desired to receive amount in cents
    :param publisher_fee: publisher fee value, in percents
    :param steam_fee: steam fee value, in percents
    :param wallet_fee_min: minimum wallet fee value, in cents
    :param wallet_fee_base: wallet fee base value, in cents
    :return: `Steam` fee value, publisher fee value, buyer pays amount
    """

    steam_fee_value = int(floor(max(amount * steam_fee, wallet_fee_min) + wallet_fee_base))
    publisher_fee_value = int(floor(max(amount * publisher_fee, 1) if publisher_fee > 0 else 0))
    return steam_fee_value, publisher_fee_value, int(amount + steam_fee_value + publisher_fee_value)


def buyer_pays_to_receive(
    amount: int,
    *,
    publisher_fee: float = 0.10,
    steam_fee: float = 0.05,
    wallet_fee_min: float = 1,
    wallet_fee_base: float = 0,
) -> tuple[int, int, int]:
    """
    Convert `buyer_pays` amount to `to_receive`. Mostly needed for placing sell listing.
    Works just like function from sell listing window on `Steam`.

    :param amount: desired amount, that buyer must pay, in cents
    :param publisher_fee: publisher fee value, in percents
    :param steam_fee: steam fee value, in percents
    :param wallet_fee_min: minimum wallet fee value, in cents
    :param wallet_fee_base: wallet fee base value, in cents
    :return: `Steam` fee value, publisher fee value, amount to receive
    """

    # I don't know how it works, it's just a copy of js function working on inputs in steam front
    estimated_amount = int((amount - wallet_fee_base) / (steam_fee + publisher_fee + 1))
    s_fee, p_fee, v = receive_to_buyer_pays(
        estimated_amount,
        publisher_fee=publisher_fee,
        steam_fee=steam_fee,
        wallet_fee_min=wallet_fee_min,
        wallet_fee_base=wallet_fee_base,
    )

    i = 0
    some_flag = False
    while (v != amount) and (i < 10):
        if v > amount:
            if some_flag:
                s_fee, p_fee, v = receive_to_buyer_pays(
                    estimated_amount - 1,
                    publisher_fee=publisher_fee,
                    steam_fee=steam_fee,
                    wallet_fee_min=wallet_fee_min,
                    wallet_fee_base=wallet_fee_base,
                )
                s_fee += amount - v
                v = amount
                break
            else:
                estimated_amount -= 1
        else:
            some_flag = True
            estimated_amount += 1

        s_fee, p_fee, v = receive_to_buyer_pays(
            estimated_amount,
            publisher_fee=publisher_fee,
            steam_fee=steam_fee,
            wallet_fee_min=wallet_fee_min,
            wallet_fee_base=wallet_fee_base,
        )
        i += 1

    return s_fee, p_fee, int(v - s_fee - p_fee)


# https://github.com/DoctorMcKay/node-steam-session/blob/a13bdf1e9c9a42c17a13db2b6be269e0c740fb07/src/LoginSession.ts#L807
def generate_session_id() -> str:
    """Generate steam like session id."""

    return token_hex(12)


def decode_jwt(token: str) -> JWTToken:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT", parts)

    return j_loads(b64decode(parts[1] + "==", altchars="-_"))


def find_item_name_id_in_text(text: str) -> int | None:
    """Find and return`item name id` in HTML text response from `Steam Community Market` item page."""

    res = re_search(r"Market_LoadOrderSpread\(\s?(?P<nameid>\d+)\s?\)", text)  # no need to precompile
    return int(res["nameid"]) if res is not None else res


_HEADER_TIME_FORMAT = "%a, %d %b %Y %H:%M:%S %Z"


def parse_time(value: str) -> datetime:
    """
    Parse header time (`Last-Modified`, `Expires`, ...),
    cookie `expires` fields to a timezone naive datetime object
    """

    return datetime.strptime(value, _HEADER_TIME_FORMAT)


def format_time(d: datetime) -> str:
    """Format timezone naive datetime object to header/cookie acceptable string"""

    return d.strftime(_HEADER_TIME_FORMAT) + "GMT"  # simple case


# generic, but less performant due to getattr
# without typing, PyCharm complains about return type while VsCode not


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


def calc_market_listing_fee(price: int, *, wallet_fee=0.05, publisher_fee=0.10, minimal_fee=1) -> int:
    """
    Calculate total market fee for listing.

    Use `get_wallet_info` method of the client to see fees values for specified `Steam` account

    :param price: price of market listing without fee (subtotal)
    :param wallet_fee: steam fee. Defaults to 0.05 (5%)
    :param publisher_fee: app publisher fee. Defaults to 0.10 (10%)
    :param minimal_fee: minimal fee value
    :return: calculated fee of price as integer
    """

    return (floor(price * wallet_fee) or minimal_fee) + (floor(price * publisher_fee) or minimal_fee)


# TODO how about merge this with transport.add_cookie?
def create_cookie(
    domain: str,
    name: str,
    value: str,
    *,
    path="/",
    expires: datetime | str = None,
    samesite: str | Literal[True] = None,
    secure: bool = False,
    httponly: bool = False,
) -> SimpleCookie:
    c = SimpleCookie()
    c[name] = value
    c[name]["path"] = path
    c[name]["domain"] = domain
    if expires is not None:
        if isinstance(expires, datetime):
            c[name]["expires"] = format_time(expires)
        else:  # str
            c[name]["expires"] = expires
    if samesite is not None:
        c[name]["samesite"] = samesite
    if secure:
        c[name]["secure"] = secure
    if httponly:
        c[name]["httponly"] = httponly

    return c


# def create_morsel():
#     c[name] = value
#     c[name]["path"] = path
#     c[name]["domain"] = domain
#     if expires is not None:
#         if isinstance(expires, datetime):
#             c[name]["expires"] = format_time(expires)
#         else:  # str
#             c[name]["expires"] = expires
#     if samesite is not None:
#         c[name]["samesite"] = samesite
#     if secure:
#         c[name]["secure"] = secure
#     if httponly:
#         c[name]["httponly"] = httponly
#
#     return c
