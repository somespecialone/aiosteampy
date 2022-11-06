class InvalidCredentials(Exception):
    pass


class CaptchaRequired(Exception):
    pass


class LoginError(Exception):
    pass


class ApiError(Exception):
    pass
