import asyncio
from base64 import b64decode, b64encode
from struct import pack, unpack
from time import time as time_time
from hmac import new as hmac_new
from hashlib import sha1
from functools import wraps
from typing import Callable, Coroutine, overload

from bs4 import BeautifulSoup
from aiohttp import ClientSession
from yarl import URL


__all__ = (
    "gen_two_factor_code",
    "generate_confirmation_key",
    "generate_device_id",
    "do_session_steam_auth",
    "get_cookie_value_from_session",
    "async_throttle",
)


def gen_two_factor_code(shared_secret: str, timestamp: int = None) -> str:
    """
    Generate twofactor code
    """
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
    hexed_steam_id = sha1(str(steam_id).encode("ascii")).hexdigest()
    return "android:" + "-".join(
        [hexed_steam_id[:8], hexed_steam_id[8:12], hexed_steam_id[12:16], hexed_steam_id[16:20], hexed_steam_id[20:32]]
    )


async def do_session_steam_auth(session: ClientSession, auth_url: str | URL):
    """
    Request auth page, find specs of steam openid and log in through steam with passed session.
    """
    resp = await session.get(auth_url)
    text = await resp.text()

    soup = BeautifulSoup(text, "html.parser")
    form = soup.find(id="openidForm")
    login_data = {
        "action": form.find(id="actionInput").attrs["value"],
        "openid.mode": form.find(attrs={"name": "openid.mode"}).attrs["value"],
        "openidparams": form.find(attrs={"name": "openidparams"}).attrs["value"],
        "nonce": form.find(attrs={"name": "nonce"}).attrs["value"],
    }

    await session.post("https://steamcommunity.com/openid/login", data=login_data)


def get_cookie_value_from_session(session: ClientSession, domain: str, field: str) -> str | None:
    """
    This function exists only to hide annoying alert `unresolved _cookies attr reference` from main base code.
    """
    if field in session.cookie_jar._cookies[domain]:
        return session.cookie_jar._cookies[domain][field].value


@overload
def async_throttle(seconds: float, *, arg_index: int):
    ...


@overload
def async_throttle(seconds: float, *, arg_name: str):
    ...


@overload
def async_throttle(seconds: float):
    ...


def async_throttle(seconds: float, *, arg_index: int = None, arg_name: str = None):
    """
    Decorator, `await sleep` before call wrapped async func,
    when related arg was equal (same hash value) to related arg passed in previous func call.
    Related arg must be hashable (can be dict key).
    Wrapped func must be async (return Coroutine).
    Throttle every func call time if related arg has been not specified.
    :param seconds: seconds to await
    :param arg_index: index of related arg in *args tuple
    :param arg_name: keyname of related arg in **kwargs
    """

    def decorator(f: Callable[..., Coroutine]):
        ts_map: dict[..., float] = {}
        # TODO maybe asyncio.lock is better and more accurate solution

        @wraps(f)
        async def wrapper(*args, **kwargs):
            key = args[arg_index] if arg_index is not None else kwargs[arg_name]
            prev_ts = ts_map[key] if key in ts_map else 0
            ts = time_time()
            diff = ts - prev_ts
            if diff < seconds:
                await asyncio.sleep(diff + 0.01)  # +10ms to ensure that second passed since last call
                ts_map[key] = time_time()
            else:
                ts_map[key] = ts

            return await f(*args, **kwargs)

        return wrapper

    return decorator
