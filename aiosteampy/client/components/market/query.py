from dataclasses import dataclass, field
from typing import Literal, Self

from ....transport.types import _ScalarTypes
from ...app import App
from ...constants import Currency

TFilters = dict[str, list[str]]

SortingCriteria = Literal["popularity", "name", "quantity", "price", None]
SortDir = Literal["asc", "desc"]  # 1, 2

SORTING_MAP: dict[SortingCriteria, int] = {
    "popularity": 0,
    "name": 1,
    "quantity": 2,
    "price": 3,
}


@dataclass(slots=True)
class SearchQuery:
    """Query builder for market search."""

    app: App | None = None
    """Queried ``app``."""

    query: str = ""
    """Search string ``query``."""
    descriptions: bool = False
    """Include ``descriptions`` in search."""

    price_min: int | None = None
    """Minimal `price` for results."""
    price_max: int | None = None
    """Maximal `price` for results."""

    sort_by: SortingCriteria = None
    """Sorting criteria(column)."""
    sort_dir: SortDir = "asc"
    """Sorting direction."""

    filters: TFilters = field(default_factory=dict)
    """Map of ``app`` filter facets and tags."""

    def __post_init__(self):
        if self.app is None and not self.query:
            raise ValueError("Either app or query is required")

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
        return {f"category_{self.app.id}_{cat}": [f"tag_{t}" for t in tags] for cat, tags in self.filters.items()}

    def payload(self, start: int = 0, currency: Currency = Currency.USD) -> list[dict]:
        """Build `JSON payload` for market search endpoint."""

        price = {"eCurrency": currency}
        if self.price_max is not None:
            price["unMax"] = self.price_max
        if self.price_min is not None:
            price["unMin"] = self.price_min

        # guess we do not oblige to keep original order
        payload = {
            "accessoryFilters": {},  # Does not accessible during app search but can work
            "filters": self._build_filters(),
            "price": price,
            "start": start,
            "strQuery": self.query,
        }

        if self.app:
            payload["appid"] = self.app.id
        if self.descriptions:
            payload["bSearchDescriptions"] = True
        if self.sort_by:
            payload["sort"] = SORTING_MAP[self.sort_by]
            payload["direction"] = 1 if self.sort_dir == "asc" else 2

        return [payload]

    def params(self, currency: Currency = Currency.USD) -> list[tuple[str, _ScalarTypes]]:
        """Build `url query params` for market search endpoint."""

        params = []
        # attempt to keep original order
        if self.price_min is not None or self.price_max is not None:
            params.append(("price_currency", currency))
        if self.price_min is not None:
            params.append(("price_min", self.price_min))
        if self.price_max is not None:
            params.append(("price_max", self.price_max))

        if self.app:
            params.extend((facet, tag) for facet, tags in self._build_filters().items() for tag in tags)
            params.append(("appid", self.app.id))

        self.query and params.append(self.query)
        self.descriptions and params.append(("descriptions", "1"))

        if self.sort_by:
            params.append(("sort", SORTING_MAP[self.sort_by]))
            params.append(("dir", 1 if self.sort_dir == "asc" else 2))

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
