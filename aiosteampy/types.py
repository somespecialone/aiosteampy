"""Shared types."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import App
    from .models import ItemDescription


AppMap = dict[int, "App"]
ItemDescriptionsMap = dict[str, "ItemDescription"]  # ident code : descr
