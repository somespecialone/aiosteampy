"""
Tests for the fix to _parse_assets_for_history_listings:
When an asset has a different unowned_contextid vs contextid (e.g. CS2 items),
the econ_item_map key must use unowned_contextid so that _parse_history_listings
can look the item up without a KeyError.

Reproduces: https://github.com/somespecialone/aiosteampy/issues/<TBD>
"""

import pytest
from unittest.mock import MagicMock

from aiosteampy.mixins.market import MarketMixin
from aiosteampy.utils import create_ident_code


# Minimal item description stub
def _make_item_descrs_map(app_id: str, classid: str, instanceid: str) -> dict:
    stub = MagicMock()
    key = create_ident_code(instanceid, classid, app_id)
    return {key: stub}


class TestParseAssetsForHistoryListings:
    """
    Reproduces the KeyError triggered by Steam returning assets where
    contextid (e.g. "2") differs from unowned_contextid (e.g. "16").

    Before the fix, _parse_assets_for_history_listings used the outer-loop
    context_id ("2") when building key_unowned_id, producing:
        "49905180787:2:730"

    But _parse_history_listings looked up using asset["contextid"] from the
    listing data ("16"), expecting:
        "49905180787:16:730"

    This mismatch caused a KeyError.
    """

    # Minimal assets payload mirroring the real Steam response structure
    ASSETS = {
        "730": {
            "2": {
                "49905180787": {
                    "currency": 0,
                    "appid": 730,
                    "contextid": "2",
                    "id": "49905180787",
                    "classid": "7993039816",
                    "instanceid": "8194180196",
                    "amount": "0",
                    "status": 4,
                    "original_amount": "1",
                    "unowned_id": "49905180787",
                    "unowned_contextid": "16",  # <-- differs from contextid!
                    "background_color": "2d3042",
                    "icon_url": "fake_icon_url",
                    "rollback_new_id": "49905180787",
                    "rollback_new_contextid": "2",
                }
            }
        }
    }

    def setup_method(self):
        self.item_descrs_map = _make_item_descrs_map("730", "7993039816", "8194180196")
        self.econ_item_map = {}

    def test_key_uses_unowned_contextid(self):
        """The econ_item_map must be keyed by unowned_contextid, not contextid."""
        MarketMixin._parse_assets_for_history_listings(
            self.ASSETS, self.item_descrs_map, self.econ_item_map
        )

        # Key built with contextid="2" (old, buggy behaviour)
        buggy_key = create_ident_code("49905180787", "2", "730")
        # Key built with unowned_contextid="16" (correct behaviour)
        correct_key = create_ident_code("49905180787", "16", "730")

        assert correct_key in self.econ_item_map, (
            f"econ_item_map must contain key '{correct_key}' (using unowned_contextid). "
            f"Keys present: {list(self.econ_item_map.keys())}"
        )
        # The buggy key (contextid="2") is still inserted via key_id — that's fine.
        # We just need the unowned key to be present for _parse_history_listings.

    def test_no_keyerror_in_parse_history_listings(self):
        """
        _parse_history_listings must be able to look up the item without raising KeyError.
        The listing asset uses contextid="16" (the unowned_contextid), so the map
        must have a key for "16" to avoid a crash.
        """
        MarketMixin._parse_assets_for_history_listings(
            self.ASSETS, self.item_descrs_map, self.econ_item_map
        )

        # Simulate how _parse_history_listings constructs its lookup key
        listing_asset = {"id": "49905180787", "contextid": "16", "appid": "730"}
        lookup_key = create_ident_code(
            listing_asset["id"], listing_asset["contextid"], listing_asset["appid"]
        )

        assert lookup_key in self.econ_item_map, (
            f"KeyError would occur: '{lookup_key}' not in econ_item_map. "
            f"Keys present: {list(self.econ_item_map.keys())}"
        )

    def test_key_id_also_present(self):
        """The key for the regular id/contextid should still be in the map."""
        MarketMixin._parse_assets_for_history_listings(
            self.ASSETS, self.item_descrs_map, self.econ_item_map
        )
        key_id = create_ident_code("49905180787", "2", "730")
        assert key_id in self.econ_item_map

    def test_matching_contextids_unchanged(self):
        """When contextid == unowned_contextid, behaviour should be unchanged."""
        assets_matching = {
            "730": {
                "2": {
                    "111": {
                        "currency": 0,
                        "appid": 730,
                        "contextid": "2",
                        "id": "111",
                        "classid": "9999",
                        "instanceid": "8888",
                        "amount": "1",
                        "status": 2,
                        "original_amount": "1",
                        "unowned_id": "111",
                        "unowned_contextid": "2",  # same as contextid
                        "background_color": "",
                        "icon_url": "",
                    }
                }
            }
        }
        item_descrs = _make_item_descrs_map("730", "9999", "8888")
        econ_map = {}

        MarketMixin._parse_assets_for_history_listings(assets_matching, item_descrs, econ_map)

        key = create_ident_code("111", "2", "730")
        assert key in econ_map
