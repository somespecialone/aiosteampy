"""Shared types."""

from typing import Any, TypeVar, Coroutine, NewType, TYPE_CHECKING

if TYPE_CHECKING:
    from .app import App
    from .models import ItemDescription

_T = TypeVar("_T")

CORO = Coroutine[Any, Any, _T]

AppMap = dict[int, "App"]
ItemDescriptionsMap = dict[str, "ItemDescription"]  # ident code : descr
