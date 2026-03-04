from typing import Any, Literal, Mapping, Self

JSON_SAFE_COOKIE_DICT = dict[str, str | int | bool | dict[str, Any] | None]

HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]  # will be used first two, however
Headers = Mapping[str, str]
Params = Mapping[str, Any]
Payload = Mapping[str, Any]
ResponseMode = Literal["bytes", "json", "text", "meta"]  # Enum is not worth it
