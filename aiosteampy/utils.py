import base64
import struct
import time
import hmac
from hashlib import sha1

from bs4 import BeautifulSoup
from aiohttp import ClientSession
from yarl import URL


def gen_two_factor_code(shared_secret: str, timestamp: int = None) -> str:
    """
    Generate twofactor code
    """
    if timestamp is None:
        timestamp = int(time.time())
    time_buffer = struct.pack(">Q", timestamp // 30)  # pack as Big endian, uint64
    time_hmac = hmac.new(base64.b64decode(shared_secret), time_buffer, digestmod=sha1).digest()
    begin = ord(time_hmac[19:20]) & 0xF
    full_code = struct.unpack(">I", time_hmac[begin : begin + 4])[0] & 0x7FFFFFFF  # unpack as Big endian uint32
    chars = "23456789BCDFGHJKMNPQRTVWXY"
    code = ""

    for _ in range(5):
        full_code, i = divmod(full_code, len(chars))
        code += chars[i]

    return code


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
