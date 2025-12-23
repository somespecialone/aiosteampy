from .models import TransportResponse


class TransportError(Exception):
    """Raise when transport is unable to process request or response or get error status code."""

    def __init__(self, response: TransportResponse | None = None):
        self.response = response
