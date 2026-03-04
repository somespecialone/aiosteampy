from secrets import token_hex

from yarl import URL


def parse_qr_challenge_url(url: URL | str) -> tuple[int, int]:
    """Parse QR challenge url. Return `version` and `client id`."""

    version, client_id = URL(url).path.split("/")
    return int(version), int(client_id)


def generate_session_id() -> str:
    """Generate `Steam` like session id."""

    return token_hex(12)
