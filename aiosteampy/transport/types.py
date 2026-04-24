from collections.abc import Mapping, Sequence
from typing import Literal

HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]  # will be used first two, however
Headers = Mapping[str, str]
_ScalarTypes = str | int | float
Query = Mapping[str, _ScalarTypes] | Sequence[tuple[str, _ScalarTypes]]
FormPayload = Query
MultipartPayload = Mapping[str, _ScalarTypes]
JsonPayload = int | float | bool | list | dict | None
ResponseMode = Literal["bytes", "json", "text", "meta"]  # Enum is not worth it
Content = str | bytes | JsonPayload
