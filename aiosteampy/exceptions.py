class ApiError(Exception):
    """Raises when there is a problem with calling steam web/api methods (mostly due to `success` field)"""

    def __init__(self, msg: str, error_code: int | None = None, data=None):
        self.msg = msg
        self.error_code = error_code
        self.data = data


class SessionExpired(Exception):
    """Raised when session is expired, and you need to do login."""
