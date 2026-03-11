from base64 import b64encode
from secrets import token_hex

from rsa import PublicKey
from rsa import encrypt as rsa_encrypt
from yarl import URL


def parse_qr_challenge_url(url: URL | str) -> tuple[int, int]:
    """Parse QR challenge url. Return `version` and `client id`."""

    version, client_id = URL(url).path.split("/")
    return int(version), int(client_id)


def generate_session_id() -> str:
    """Generate `Steam` like session id."""

    return token_hex(12)


def encrypt_password(password: str, pub_mod: int, pub_exp: int) -> str:
    """Encrypt password with RSA."""

    return b64encode(rsa_encrypt(password.encode("utf-8"), PublicKey(pub_mod, pub_exp))).decode()
