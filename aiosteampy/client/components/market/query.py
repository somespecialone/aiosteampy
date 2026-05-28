from base64 import b64encode
from dataclasses import dataclass, field
from typing import Literal, Self, overload

import betterproto2

from ....transport.types import _ScalarTypes
from ...app import App
from ...constants import Currency

TFilters = dict[str, list[str]]

# confusing as ....
SortDir = Literal["asc", "desc"]
SearchSorting = Literal["popularity", "name", "quantity", "price", None]
ListingsSorting = Literal["price", None] | int

SEARCH_SORTING_MAP: dict[SearchSorting, int] = {
    "popularity": 0,
    "name": 1,
    "quantity": 2,
    "price": 3,
}


# Only for SearchQuery and ListingsQuery structure/shared functionality inheriting
@dataclass(slots=True, kw_only=True)
class BaseQuery:
    """"""

    app: App | None = None
    """Queried ``app``."""

    query: str = ""
    """Search string ``query``."""

    sort_dir: SortDir = "asc"
    """Sorting direction."""

    price_min: int | None = None
    """Minimal `price` for results."""
    price_max: int | None = None
    """Maximal `price` for results."""

    filters: TFilters = field(default_factory=dict)
    """Map of ``app`` filter facets and tags."""

    def filter(self, facet: str, *tags: str) -> Self:
        """
        Add ``facet`` with ``tags`` to `query`.

        .. note:: App id, 'category' and 'tag' keywords **must be excluded**.

        For example, to set ``CS2`` `StatTrak` quality ``facet`` need to be 'Quality'
        and tag 'strange'.
        """

        if self.app is None:
            raise ValueError("app is required to set filter facets")

        self.filters.setdefault(facet, []).extend(tags)
        return self

    def _build_filters(self) -> TFilters:
        return {f"category_{self.app.id}_{f}": [f"tag_{t}" for t in tags] for f, tags in self.filters.items()}

    def _payload(self, start: int, currency: Currency) -> dict:
        price = {"eCurrency": currency}
        if self.price_max is not None:
            price["unMax"] = self.price_max
        if self.price_min is not None:
            price["unMin"] = self.price_min

        # guess we do not oblige to keep original order
        payload = {
            "accessoryFilters": {},  # as browser
            "filters": self._build_filters(),
            "price": price,
            "start": start,
        }

        if self.app:
            payload["appid"] = self.app.id
        if self.query:
            payload["strQuery"] = self.query

        return payload

    def _params(self, currency: Currency) -> list[tuple[str, _ScalarTypes]]:
        params = []
        if self.price_min is not None or self.price_max is not None:
            params.append(("price_currency", currency))
        if self.price_min is not None:
            params.append(("price_min", self.price_min))
        if self.price_max is not None:
            params.append(("price_max", self.price_max))

        if self.app:
            params.extend((facet, tag) for facet, tags in self._build_filters().items() for tag in tags)
            params.append(("appid", self.app.id))

        self.query and params.append(("q", self.query))

        return params


@dataclass(slots=True)
class SearchQuery(BaseQuery):
    """
    Query builder for market search.
    Either ``app`` or ``query`` is required.
    """

    sort_by: SearchSorting = None
    """Sorting criteria(column)."""

    descriptions: bool = False
    """Include ``descriptions`` in search."""

    def __post_init__(self):
        if self.app is None and not self.query:
            raise ValueError("Either app or query is required")

    def _sort_dir(self) -> int:
        return 1 if self.sort_dir == "asc" else 2

    def payload(self, start: int = 0, currency: Currency = Currency.USD) -> list[dict]:
        """Build `JSON payload` for market search endpoint."""

        # guess we do not oblige to keep original order
        payload = self._payload(start, currency)
        if self.descriptions:
            payload["bSearchDescriptions"] = True
        if self.sort_by:
            payload["sort"] = SEARCH_SORTING_MAP[self.sort_by]
            payload["direction"] = self._sort_dir()

        return [payload]

    def params(self, currency: Currency = Currency.USD) -> list[tuple[str, _ScalarTypes]]:
        """Build `url query params` for market search endpoint."""

        # same thing regarding order
        params = self._params(currency)
        if self.sort_by:
            params.append(("sort", self.sort_by))
            params.append(("dir", self._sort_dir()))

        self.descriptions and params.append(("descriptions", "1"))

        return params

    def build(
        self,
        start: int = 0,
        currency: Currency = Currency.USD,
    ) -> tuple[list[dict], list[tuple[str, _ScalarTypes]]]:
        """Build `JSON payload` and `url query params` for market search endpoint."""
        return self.payload(start, currency), self.params(currency)

    def clear(self):
        """Clear the current `query` to the initial state. ``app`` will be kept."""

        self.query = ""
        self.descriptions = False
        self.price_min = self.price_max = self.sort_by = None
        self.sort_dir = "asc"
        self.filters.clear()


# https://github.com/SteamTracking/Protobufs/blob/e36c4b3f887e5c22bd53cee70f0b3bcb0b348f5a/webui/common.proto#L3-L9
@dataclass(eq=False, repr=False)
class AssetPropertyFilter(betterproto2.Message):
    property_id: "int" = betterproto2.field(1, betterproto2.TYPE_UINT32)
    float_min: "float" = betterproto2.field(2, betterproto2.TYPE_FLOAT)
    float_max: "float" = betterproto2.field(3, betterproto2.TYPE_FLOAT)
    int_min: "int" = betterproto2.field(4, betterproto2.TYPE_INT64)
    int_max: "int" = betterproto2.field(5, betterproto2.TYPE_INT64)


@dataclass(slots=True)
class ListingsQuery(BaseQuery):
    """
    Query builder for market listings.
    Typed builders for dedicated apps should inherit this.
    """

    sort_by: ListingsSorting = None
    """
    Sorting criteria(column).
    ``int`` can be provided as value of `assetpropertyid(app defined property)`"""

    accessories: TFilters = field(default_factory=dict)
    """Map of ``app`` accessory filter facets and tags."""

    properties: dict[int, dict[str, int | float]] = field(default_factory=dict)
    """Map of ``app`` property filter facets and payload values."""

    def _build_accessories(self) -> TFilters:
        return {f"accessory_{f}": accs for f, accs in self.accessories.items()}

    def _build_properties(self) -> dict[str, dict[str, int | float]]:
        return {str(prop_id): {"property_id": prop_id, **prop_val} for prop_id, prop_val in self.properties.items()}

    def accessory(self, facet: str, *tags: str) -> Self:
        """
        Add ``app`` specific accessory ``facet`` with ``tags`` to `query`.

        .. note:: 'accessory' keyword **must be excluded**.

        For example, to set ``CS2`` `Charm | Pocket AWP` charm(keychain) ``facet`` need to be 'CSGO_Tool_Keychain'
        and tag 'Charm | Pocket AWP'.
        """

        if self.app is None:
            raise ValueError("app is required to set accessory filter facets")

        self.accessories.setdefault(facet, []).extend(tags)
        return self

    @overload
    def property(self, id_: int, *, int_min: int, int_max: int) -> Self: ...
    @overload
    def property(self, id_: int, *, float_min: float, float_max: float) -> Self: ...
    def property(
        self,
        id_: int,
        *,
        int_min: int | None = None,
        int_max: int | None = None,
        float_min: float | None = None,
        float_max: float | None = None,
    ) -> Self:
        """
        Add ``app`` specific property filter to `query`.

        .. note:: `property_id` field will be automatically added to payload so can be omitted in ``property_``.

        For example, to set ``CS2`` `wear rating` property filter ``id_`` must be `2`
        and ``property_id`` need to be `{"float_min": 0, "float_max": 1}`.
        """

        if self.app is None:
            raise ValueError("app is required to set property filter facets")

        prop = {}
        if int_min is not None:
            prop["int_min"] = int_min
            prop["int_max"] = int_max
        else:
            prop["float_min"] = float_min
            prop["float_max"] = float_max
        self.properties[id_] = prop

    def _sort_dir(self) -> int:
        return 0 if self.sort_dir == "asc" else 1

    def _sort_by(self) -> int:
        return 0 if str(self.sort_by) == "price" else 1

    def payload(self, bucket_group_id: str, start: int = 0, currency: Currency = Currency.USD) -> list[dict]:
        """Build `JSON payload` for market listings endpoint."""

        payload = self._payload(start, currency)
        payload["strItemName"] = bucket_group_id
        payload["accessoryFilters"] = self._build_accessories()
        payload["propertyFilters"] = self._build_properties()
        if self.sort_by is not None:
            sort = {"field": self._sort_by(), "direction": self._sort_dir()}
            if isinstance(self.sort_by, int):  # sorting by app defined property
                sort["assetpropertyid"] = self.sort_by

            payload["sort"] = sort

        return [payload]

    def params(self, currency: Currency = Currency.USD) -> list[tuple[str, _ScalarTypes]]:
        """Build `url query params` for market listings endpoint."""

        params = self._params(currency)
        if self.app:
            params.extend((facet, acc) for facet, accs in self._build_accessories().items() for acc in accs)
            params.extend(
                (
                    "assetproperty",
                    b64encode(bytes(AssetPropertyFilter(**prop))).decode(),
                )
                for prop in self._build_properties().values()
            )

        if self.sort_by is not None:
            params.append(("sort", self._sort_by()))
            params.append(("dir", self._sort_dir()))
            if isinstance(self.sort_by, int):
                params.append(("propertyid", self.sort_by))

        return params

    def build(
        self,
        bucket_group_id: str,
        start: int = 0,
        currency: Currency = Currency.USD,
    ) -> tuple[list[dict], list[tuple[str, _ScalarTypes]]]:
        """Build `JSON payload` and `url query params` for market listings endpoint."""
        return self.payload(bucket_group_id, start, currency), self.params(currency)
