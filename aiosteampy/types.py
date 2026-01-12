"""Shared types."""

from typing import Any, TypeVar, NewType, TYPE_CHECKING
from collections.abc import Coroutine

if TYPE_CHECKING:
    from .app import App
    from .models import ItemDescription

_T = TypeVar("_T")

CORO = Coroutine[Any, Any, _T]

AppMap = dict[int, "App"]
ItemDescriptionsMap = dict[str, "ItemDescription"]  # ident code : descr
