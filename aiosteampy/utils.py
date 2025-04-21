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

from aiohttp import ClientSession, ClientResponse
from yarl import URL

from .typed import JWTToken


__all__ = (
    "gen_two_factor_code",
    "generate_confirmation_key",
    "generate_device_id",
    "extract_openid_payload",
    "do_session_steam_auth",
    "get_cookie_value_from_session",
    "remove_cookie_from_session",
    "async_throttle",
    "create_ident_code",
    "account_id_to_steam_id",
    "steam_id_to_account_id",
    "id64_to_id32",
    "id32_to_id64",
    "to_int_boolean",
    "get_jsonable_cookies",
    "update_session_cookies",
    "buyer_pays_to_receive",
    "receive_to_buyer_pays",
    "generate_session_id",
    "decode_jwt",
    "find_item_nameid_in_text",
    "patch_session_with_http_proxy",
    "parse_time",
    "format_time",
    "attribute_required",
    "make_inspect_url",
    "add_cookie_to_session",
    "calc_market_listing_fee",
)


def gen_two_factor_code(shared_secret: str, timestamp: int = None) -> str:
    """Generate twofactor (onetime/TOTP) code."""

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


def generate_confirmation_key(identity_secret: str, tag: str, timestamp: int = None) -> str:
    if timestamp is None:
        timestamp = int(time_time())
    buff = pack(">Q", timestamp) + tag.encode("ascii")
    return b64encode(hmac_new(b64decode(identity_secret), buff, digestmod=sha1).digest()).decode()


# It works, however it's different that one generated from mobile app
def generate_device_id(steam_id: int) -> str:
    """Generate mobile android device id. Confirmation endpoints requires this."""

    hexed_steam_id = sha1(str(steam_id).encode("ascii")).hexdigest()
    return "android:" + "-".join(
        [hexed_steam_id[:8], hexed_steam_id[8:12], hexed_steam_id[12:16], hexed_steam_id[16:20], hexed_steam_id[20:32]]
    )


def extract_openid_payload(page_text: str) -> dict[str, str]:
    """
    Extract steam openid payload (specs) from page html raw text.
    Use it if 3rd party websites have extra or non-cookie auth (JWT via service API call, for ex.).

    :param page_text:
    :return: dict with payload data
    """

    # not so beautiful as with bs4 but dependency free
    return {
        "action": re_search(r"id=\"actionInput\"[\w=\"\s]+value=\"(?P<action>\w+)\"", page_text)["action"],
        "openid.mode": re_search(r"name=\"openid\.mode\"[\w=\"\s]+value=\"(?P<mode>\w+)\"", page_text)["mode"],
        "openidparams": re_search(r"name=\"openidparams\"[\w=\"\s]+value=\"(?P<params>[\w=/]+)\"", page_text)["params"],
        "nonce": re_search(r"name=\"nonce\"[\w=\"\s]+value=\"(?P<nonce>\w+)\"", page_text)["nonce"],
    }


async def do_session_steam_auth(session: ClientSession, auth_url: str | URL) -> ClientResponse:
    """
    Request auth page, find specs of steam openid and log in through steam with passed session.
    Use it when you need to log in 3rd party site trough Steam using only cookies.

    .. seealso:: https://aiosteampy.somespecial.one/examples/auth_3rd_party_site/

    :param session: just session.
    :param auth_url: url to site, which redirect you to steam login page.
    :return: response with history, headers and data
    """

    r = await session.get(auth_url)
    rt = await r.text()

    data = extract_openid_payload(rt)

    return await session.post("https://steamcommunity.com/openid/login", data=data, allow_redirects=True)


def get_cookie_value_from_session(session: ClientSession, url: URL | str, field: str) -> str | None:
    """Get value from session cookies. Passed `url` must include scheme (for ex. `https://url.com`)."""

    c = session.cookie_jar.filter_cookies(URL(url))
    return c[field].value if field in c else None


def remove_cookie_from_session(session: ClientSession, url: URL | str, field: str) -> bool:
    """Remove cookie from session cookies. Return `True` if cookie was present and removed."""

    raw = str(url)
    if "//" in raw:
        host = raw.split("//")[1]
    else:
        host = raw
    return bool(session.cookie_jar._cookies[(host, "/")].pop(field, None))


_R = TypeVar("_R")


@overload
def async_throttle(seconds: float, *, arg_index: int) -> Callable[[Callable[..., _R]], Callable[..., _R]]:
    ...


@overload
def async_throttle(seconds: float, *, arg_name: str) -> Callable[[Callable[..., _R]], Callable[..., _R]]:
    ...


@overload
def async_throttle(seconds: float) -> Callable[[Callable[..., _R]], Callable[..., _R]]:
    ...


def async_throttle(seconds, *, arg_index=None, arg_name=None):
    """
    Prevents the decorated function from being called more than once per `seconds`.
    Throttle (`await asyncio.sleep`) before call wrapped async func,
    when related arg was equal (same hash value) to related arg passed in previous func call
    if time between previous and current call lower than `seconds`.
    Related arg must be hashable (can be dict key).
    Wrapped func must be async (return `Coroutine`).
    Throttle every func call time if related arg has been not specified.

    :param seconds: seconds during which call frequency has been limited.
    :param arg_index: index of related arg in *args tuple.
    :param arg_name: keyname of related arg in **kwargs.
    """

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


@overload
def create_ident_code(asset_id: int | str, context_id: int | str, app_id: int | str, *, sep: str = ...) -> str:
    ...


@overload
def create_ident_code(instance_id: int | str, class_id: int | str, app_id: int | str, *, sep: str = ...) -> str:
    ...


def create_ident_code(*args, sep=":"):
    """
    Create unique ident code for `EconItem` asset or `ItemDescription` within whole `Steam Economy`.

    .. seealso:: https://dev.doctormckay.com/topic/332-identifying-steam-items/
    """

    return sep.join(reversed(list(str(i) for i in filter(lambda i: i is not None, args))))


def steam_id_to_account_id(steam_id: int) -> int:
    """Convert steam id64 to steam id32."""

    return steam_id & 0xFFFFFFFF


def account_id_to_steam_id(account_id: int) -> int:
    """Convert steam id32 to steam id64."""

    return 1 << 56 | 1 << 52 | 1 << 32 | account_id


id64_to_id32 = steam_id_to_account_id
id32_to_id64 = account_id_to_steam_id


def to_int_boolean(s):
    """Convert something to 1, 0."""

    return 1 if s else 0


JSONABLE_COOKIE_JAR: TypeAlias = list[dict[str, dict[str, str, None, bool]]]


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


def get_jsonable_cookies(session: ClientSession) -> JSONABLE_COOKIE_JAR:
    """Extract and convert cookies to dict object."""

    return [
        {
            field_key: {
                "coded_value": morsel.coded_value,
                "key": morsel.key,
                "value": morsel.value,
                "expires": morsel["expires"],
                "path": morsel["path"],
                "comment": morsel["comment"],
                "domain": morsel["domain"],
                "max-age": morsel["max-age"],
                "secure": morsel["secure"],
                "httponly": morsel["httponly"],
                "version": morsel["version"],
                "samesite": morsel["samesite"],
            }
            for field_key, morsel in cookie.items()
        }
        for cookie in session.cookie_jar._cookies.values()
        if cookie  # skip empty cookies
    ]


def receive_to_buyer_pays(
    amount: int,
    *,
    publisher_fee=0.10,
    steam_fee=0.05,
    wallet_fee_min=1,
    wallet_fee_base=0,
) -> tuple[int, int, int]:
    """
    Convert `to_receive` amount to `buyer_pays`. Mostly needed for placing sell listing.
    Works just like function from sell listing window on `Steam`.

    :param amount: desired to receive amount in cents
    :return: `Steam` fee value, publisher fee value, buyer pays amount
    """

    steam_fee_value = int(floor(max(amount * steam_fee, wallet_fee_min) + wallet_fee_base))
    publisher_fee_value = int(floor(max(amount * publisher_fee, 1) if publisher_fee > 0 else 0))
    return steam_fee_value, publisher_fee_value, int(amount + steam_fee_value + publisher_fee_value)


def buyer_pays_to_receive(
    amount: int,
    *,
    publisher_fee=0.10,
    steam_fee=0.05,
    wallet_fee_min=1,
    wallet_fee_base=0,
) -> tuple[int, int, int]:
    """
    Convert `buyer_pays` amount to `to_receive`. Mostly needed for placing sell listing.
    Works just like function from sell listing window on `Steam`.

    :param amount: desired amount, that buyer must pay, in cents
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


# https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/LoginSession.ts#L801C19-L801C50
def generate_session_id() -> str:
    """Generate steam like session id."""

    # Hope ChatGPT knows what she is doing
    return token_hex(12)


def decode_jwt(token: str) -> JWTToken:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT", parts)

    return j_loads(b64decode(parts[1] + "==", altchars="-_"))


_ITEM_NAMEID_RE = re_compile(r"Market_LoadOrderSpread\(\s?(?P<nameid>\d+)\s?\)")


def find_item_nameid_in_text(text: str) -> int | None:
    """Find and return`item_nameid` in HTML text response from `Steam Community Market` page"""

    res = _ITEM_NAMEID_RE.search(text)
    return int(res["nameid"]) if res is not None else res


def patch_session_with_http_proxy(session: ClientSession, proxy: str | URL) -> ClientSession:
    """Patch `aiohttp.ClientSession` to make all requests go through web proxy"""

    session._request = partial(session._request, proxy=proxy)
    return session


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
def attribute_required(attr: str, msg: str = None):
    """Generate a decorator that check required `attr` on instance before call a wrapped method"""

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if getattr(self, attr, None) is None:
                raise AttributeError(msg or f"You must provide a value for '{attr}' before using this method")
            return func(self, *args, **kwargs)

        return wrapper

    return decorator


@overload
def make_inspect_url(*, owner_id: int, asset_id: int, d_id: int) -> str:
    ...


@overload
def make_inspect_url(*, market_id: int, asset_id: int, d_id: int) -> str:
    ...


def make_inspect_url(*, market_id: int = None, owner_id: int = None, asset_id: int, d_id: int) -> str:
    if market_id:
        return f"steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20M{market_id}A{asset_id}D{d_id}"
    else:
        return f"steam://rungame/730/76561202255233023/+csgo_econ_action_preview%20S{owner_id}A{asset_id}D{d_id}"


def add_cookie_to_session(
    session: ClientSession,
    url: URL | str,
    name: str,
    value: str,
    *,
    path="/",
    expires: datetime | str = None,
    samesite: str | Literal[True] = None,
    secure: bool = False,
    httponly: bool = False,
):
    if isinstance(url, str):
        url = URL(url)

    c = SimpleCookie()
    c[name] = value
    c[name]["path"] = path
    c[name]["domain"] = url.host
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

    session.cookie_jar.update_cookies(cookies=c, response_url=url)


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
