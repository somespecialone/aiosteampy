from collections.abc import Mapping
from typing import Any, Literal

HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]  # will be used first two, however
Headers = Mapping[str, str]
Params = Mapping[str, Any]
Payload = Mapping[str, Any]
ResponseMode = Literal["bytes", "json", "text", "meta"]  # Enum is not worth it
JsonContent = int | float | bool | list | dict | None
Content = str | bytes | JsonContent
