from datetime import datetime


_HEADER_TIME_FORMAT = "%a, %d %b %Y %H:%M:%S %Z"


def parse_http_date(date: str) -> datetime:
    """
    Parse HTTP header/cookie time to a timezone naive datetime object
    """

    return datetime.strptime(date, _HEADER_TIME_FORMAT)


def format_http_date(d: datetime) -> str:
    """Format timezone naive datetime object to an HTTP header/cookie acceptable string"""

    return d.strftime(_HEADER_TIME_FORMAT) + "GMT"  # simple case
