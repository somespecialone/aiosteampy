from datetime import datetime

from aiohttp.helpers import parse_http_date  # export

HEADER_TIME_FORMAT = "%a, %d %b %Y %H:%M:%S %Z"


def format_http_date(d: datetime) -> str:
    """Format timezone naive datetime object to an HTTP header acceptable string."""

    return d.strftime(HEADER_TIME_FORMAT) + "GMT"  # simple case
