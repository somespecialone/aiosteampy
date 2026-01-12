"""Common shared functionality for components."""

from collections.abc import Iterable

from ..app import App
from ..types import AppMap
from ..models import (
    AssetProperty,
    AssetAccessory,
    ItemDescriptionEntry,
    ItemTag,
    ItemAction,
    ItemDescription,
)


class EconMixin:
    """``ItemDescription``, ``EconItem`` creation related methods."""

    __slots__ = ()

    @staticmethod
    def _parse_item_actions(actions: Iterable[dict]) -> tuple[ItemAction, ...]:
        return tuple(ItemAction(a_data["link"], a_data["name"]) for a_data in actions)

    @staticmethod
    def _parse_item_tags(tags: Iterable[dict]) -> tuple[ItemTag, ...]:
        return tuple(
            ItemTag(
                t_data["category"],
                t_data["internal_name"],
                t_data["localized_category_name"],
                t_data["localized_tag_name"],
                t_data.get("color"),
            )
            for t_data in tags
        )

    @staticmethod
    def _parse_item_descr_entries(descriptions: Iterable[dict]) -> tuple[ItemDescriptionEntry, ...]:
        return tuple(
            ItemDescriptionEntry(
                d_data["value"],
                d_data.get("type"),
                d_data.get("name"),
                d_data.get("color"),
            )
            for d_data in descriptions
            if (d_data["value"] != " " and d_data["value"])  # let's omit "blank" descriptions
        )

    @classmethod
    def _create_item_descr(cls, data: dict, app_map: AppMap) -> ItemDescription:
        market_fee_app = None
        if "market_fee_app" in data:
            if app_from_map := app_map.get(data["market_fee_app"]):
                market_fee_app = app_from_map
            else:
                market_fee_app = App(data["market_fee_app"])  # any place where we can get app name
                app_map[market_fee_app.id] = market_fee_app

        return ItemDescription(
            class_id=int(data["classid"]),
            instance_id=int(data["instanceid"]),
            app=app_map[data["appid"]],
            name=data["name"],
            market_name=data["market_name"],
            market_hash_name=data["market_hash_name"],
            name_color=data.get("name_color") or None,  # ignore " "
            background_color=data.get("name_color") or None,
            type=data["type"] or None,
            icon=data["icon_url"],
            icon_large=data.get("icon_url_large"),
            commodity=bool(data["commodity"]),
            tradable=bool(data["tradable"]),
            # market search page descriptions may miss this so True by default
            marketable=bool(data.get("marketable", True)),
            market_tradable_restriction=data.get("market_tradable_restriction", 0),
            market_buy_country_restriction=data.get("market_buy_country_restriction"),
            market_fee_app=market_fee_app,
            market_marketable_restriction=data.get("market_marketable_restriction", 0),
            actions=cls._parse_item_actions(data.get("actions", ())),
            market_actions=cls._parse_item_actions(data.get("market_actions", ())),
            owner_actions=cls._parse_item_actions(data.get("owner_actions", ())),
            tags=cls._parse_item_tags(data.get("tags", ())),
            descriptions=cls._parse_item_descr_entries(data.get("descriptions", ())),
            owner_descriptions=(cls._parse_item_descr_entries(data.get("owner_descriptions", ()))),
            fraud_warnings=tuple(data.get("fraudwarnings", ())),
            sealed=bool(data["sealed"]),
        )

    @staticmethod
    def _create_property(data: dict[str, str | int]) -> AssetProperty:
        _, value = next(filter(lambda kv: kv[0].endswith("_value"), data.items()))

        return AssetProperty(data["propertyid"], value, data.get("name"))

    @classmethod
    def _parse_asset_properties(cls, data: dict) -> tuple[AssetProperty, ...]:
        """Extract ``AssetProperty`` from data."""

        # avoid iterating over present None, that's Steam
        return tuple(cls._create_property(p_data) for p_data in (data.get("asset_properties", ()) or ()))

    @classmethod
    def _create_accessory(cls, data: dict) -> AssetAccessory:
        parent_props = tuple(cls._create_property(pd) for pd in data.get("parent_relationship_properties", ()))
        standalone_props = tuple(cls._create_property(pd) for pd in data.get("standalone_properties", ()))

        return AssetAccessory(int(data["classid"]), parent_props, standalone_props)

    @classmethod
    def _parse_asset_accessories(cls, data: dict) -> tuple[AssetAccessory, ...]:
        return tuple(cls._create_accessory(a_data) for a_data in data.get("asset_accessories", ()) or ())
