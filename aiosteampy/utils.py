"""Useful utils."""

import asyncio
from base64 import b64decode, b64encode
from struct import pack, unpack
from time import time as time_time
from hmac import new as hmac_new
from hashlib import sha1
from functools import wraps
from typing import Callable, overload, ParamSpec, TypeVar, TYPE_CHECKING, TypeAlias
from http.cookies import SimpleCookie, Morsel
from math import floor
from secrets import token_hex
from re import search as re_search, compile as re_compile
from json import loads as j_loads

from aiohttp import ClientSession, ClientResponse
from yarl import URL

from .typed import JWTToken

if TYPE_CHECKING:
    from .client import SteamCommunityMixin

__all__ = (
    "gen_two_factor_code",
    "generate_confirmation_key",
    "generate_device_id",
    "extract_openid_payload",
    "do_session_steam_auth",
    "get_cookie_value_from_session",
    "async_throttle",
    "create_ident_code",
    "account_id_to_steam_id",
    "steam_id_to_account_id",
    "id64_to_id32",
    "id32_to_id64",
    "to_int_boolean",
    "restore_from_cookies",
    "get_jsonable_cookies",
    "update_session_cookies",
    "buyer_pays_to_receive",
    "receive_to_buyer_pays",
    "generate_session_id",
    "decode_jwt",
    "find_item_nameid_in_text",
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
    """
    Get value from session cookies.
    Passed `url` must include scheme (for ex. `https://url.com`)
    """

    c = session.cookie_jar.filter_cookies(URL(url))
    return c[field].value if field in c else None


_P = ParamSpec("_P")
_R = TypeVar("_R")


@overload
def async_throttle(seconds: float, *, arg_index: int):
    ...


@overload
def async_throttle(seconds: float, *, arg_name: str):
    ...


@overload
def async_throttle(seconds: float):
    ...


def async_throttle(
    seconds: float,
    *,
    arg_index: int = None,
    arg_name: str = None,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
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

    def decorator(f: Callable[_P, _R]) -> Callable[_P, _R]:
        @wraps(f)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
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


def create_ident_code(obj_id: int | str, app_id: int | str, context_id: int | str = None) -> str:
    """
    Create unique ident code for :class:`aiosteampy.models.EconItem` asset or item class
    (description) within whole Steam Economy.

    .. seealso:: https://dev.doctormckay.com/topic/332-identifying-steam-items/

    :param obj_id: asset or class id of Steam Economy Item
    :param app_id: app id of Steam Game
    :param context_id: context id of Steam Game. Only for `EconItem`
    :return: ident code
    """

    code = f"{obj_id}_{app_id}"
    if context_id is not None:
        code += f"_{context_id}"

    return code


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


def update_session_cookies(cookies: JSONABLE_COOKIE_JAR, session: ClientSession):
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


async def restore_from_cookies(
    cookies: JSONABLE_COOKIE_JAR,
    client: "SteamCommunityMixin",
    *,
    init_data=True,
    **init_kwargs,
) -> bool:
    """
    Helper func. Restore client session from cookies.
    Login if session is not alive.
    Return `True` if cookies are valid and not expired.
    """

    update_session_cookies(cookies, client.session)

    # find access token
    for cookie_data in cookies:
        for k, v in cookie_data.items():
            if v["key"] == "steamLoginSecure":
                try:
                    client._access_token = v["value"].split("%7C%7C")[1]
                    break
                except IndexError:
                    pass

    if not (await client.is_session_alive()):
        await client.login(init_data=init_data, **init_kwargs)
        return False
    else:
        client._is_logged = True
        init_data and await client._init_data()
        return True


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
    ]


def receive_to_buyer_pays(
    amount: int,
    *,
    publisher_fee=0.1,
    steam_fee=0.05,
    wallet_fee_min=1,
    wallet_fee_base=0,
) -> tuple[int, int, int]:
    """
    Convert `to_receive` amount in `buyer_pays`. Mostly needed for placing sell listing.
    Works just like on sell listing window on steam.

    :param amount: amount in cents
    :return: steam fee value, publisher fee value, buyer pays amount
    """

    steam_fee_value = int(floor(max(amount * steam_fee, wallet_fee_min) + wallet_fee_base))
    publisher_fee_value = int(floor(max(amount * publisher_fee, 1) if publisher_fee > 0 else 0))
    return steam_fee_value, publisher_fee_value, int(amount + steam_fee_value + publisher_fee_value)


def buyer_pays_to_receive(
    amount: int,
    *,
    publisher_fee=0.1,
    steam_fee=0.05,
    wallet_fee_min=1,
    wallet_fee_base=0,
) -> tuple[int, int, int]:
    """
    Convert `buyer_pays` amount in `to_receive`. Mostly needed for placing sell listing.
    Works just like on sell listing window on steam.

    :param amount: amount in cents
    :return: steam fee value, publisher fee value, amount to receive
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


def generate_session_id() -> str:
    """
    Generate steam like session id.

    .. seealso:: https://github.com/DoctorMcKay/node-steam-session/blob/698469cdbad3e555dda10c81f580f1ee3960156f/src/LoginSession.ts#L801C19-L801C50
    """

    # Hope ChatGPT knows what she is doing
    return token_hex(12)


def decode_jwt(token: str) -> JWTToken:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT", parts)

    return j_loads(b64decode(parts[1] + "==", altchars="-_"))


_ITEM_NAMEID_RE = re_compile(r"Market_LoadOrderSpread\(\s?(?P<nameid>\d+)\s?\)")


def find_item_nameid_in_text(text: str) -> int | None:
    """Find and return`item_nameid` in HTML text response from Steam Community Market page"""

    res = _ITEM_NAMEID_RE.search(text)
    return int(res["nameid"]) if res is not None else res
