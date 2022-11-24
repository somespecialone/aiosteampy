import asyncio
from base64 import b64decode, b64encode
from struct import pack, unpack
from time import time as time_time
from hmac import new as hmac_new
from hashlib import sha1
from functools import wraps
from typing import Callable, overload, ParamSpec, TypeVar, TYPE_CHECKING, TypeAlias
from http.cookies import SimpleCookie, Morsel

from bs4 import BeautifulSoup
from aiohttp import ClientSession
from yarl import URL

if TYPE_CHECKING:
    from .client import SteamCommunityMixin

__all__ = (
    "gen_two_factor_code",
    "generate_confirmation_key",
    "generate_device_id",
    "do_session_steam_auth",
    "get_session_cookie_jar",
    "get_cookie_value_from_session",
    "async_throttle",
    "create_ident_code",
    "account_id_to_steam_id",
    "steam_id_to_account_id",
    "to_int_boolean",
    "restore_from_cookies",
    "get_jsonable_cookies",
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


async def do_session_steam_auth(session: ClientSession, auth_url: str | URL):
    """
    Request auth page, find specs of steam openid and log in through steam with passed session.
    Useful when you need to log in 3rd party site trough Steam.

    :param session: just session
    :param auth_url: url to site, which redirect you to steam login page
    """

    r = await session.get(auth_url)
    rt = await r.text()

    soup = BeautifulSoup(rt, "html.parser")
    form = soup.find(id="openidForm")
    login_data = {
        "action": form.find(id="actionInput").attrs["value"],
        "openid.mode": form.find(attrs={"name": "openid.mode"}).attrs["value"],
        "openidparams": form.find(attrs={"name": "openidparams"}).attrs["value"],
        "nonce": form.find(attrs={"name": "nonce"}).attrs["value"],
    }

    await session.post("https://steamcommunity.com/openid/login", data=login_data)


def get_session_cookie_jar(session: ClientSession) -> dict[str, SimpleCookie]:
    """This function exists only to hide annoying alert "unresolved _cookies attr reference" from main base code."""

    return session.cookie_jar._cookies


def get_cookie_value_from_session(session: ClientSession, domain: str, field: str) -> str | None:
    """Just get value from session cookies."""

    jar = get_session_cookie_jar(session)
    if field in jar[domain]:
        return jar[domain][field].value


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
    seconds: float, *, arg_index: int = None, arg_name: str = None
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """
    Prevents the decorated function from being called more than once per ``seconds``.
    Throttle (`await asyncio.sleep`) before call wrapped async func,
    when related arg was equal (same hash value) to related arg passed in previous func call
    if time between previous and current call lower than ``seconds``.
    Related arg must be hashable (can be dict key).
    Wrapped func must be async (return Coroutine).
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

    https://dev.doctormckay.com/topic/332-identifying-steam-items/

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


def to_int_boolean(s):
    """Convert something to 1, 0."""

    return 1 if s else 0


JSONABLE_COOKIE_JAR: TypeAlias = list[dict[str, dict[str, str, None, bool]]]


async def restore_from_cookies(
    cookies: JSONABLE_COOKIE_JAR,
    client: "SteamCommunityMixin",
    *,
    init_data=True,
    **init_kwargs,
):
    """
    Helper func. Restore client session from cookies.
    Login if session is not alive.
    """

    prepared = []
    for cookie_data in cookies:
        c = SimpleCookie()
        for k, v in cookie_data.items():
            m = Morsel()
            m._value = v.pop("value")
            m._key = v.pop("key")
            m._coded_value = v.pop("coded_value")
            m.update(v)
            c[k] = m

        prepared.append(c)

    for c in prepared:
        client.session.cookie_jar.update_cookies(c)
    if not (await client.is_session_alive()):
        await client.login(init_data=init_data, **init_kwargs)
    else:
        client._is_logged = True
        init_data and await client._init_data()


def get_jsonable_cookies(session: ClientSession) -> JSONABLE_COOKIE_JAR:
    """Extract and convert cookies to dict object."""

    cookie_jar = get_session_cookie_jar(session)
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
        for cookie in cookie_jar.values()
    ]
