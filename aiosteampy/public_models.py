"""Models used only and only in `aiosteampy.public`"""

from typing import TypedDict, Literal


SUCCESS = Literal[0, 1]


class SellOrderTable(TypedDict):
    price: str
    price_with_fee: str
    quantity: str


class BuyOrderTable(TypedDict):
    price: str
    quantity: str


class ItemOrdersHistogram(TypedDict):
    success: SUCCESS
    sell_order_count: str
    sell_order_price: str
    sell_order_table: list[SellOrderTable]
    buy_order_count: str
    buy_order_price: str
    buy_order_table: list[BuyOrderTable]
    highest_buy_order: str
    lowest_sell_order: str

    # actually there is a lists, but tuple typing have fixed values
    buy_order_graph: list[tuple[float, int, str]]
    sell_order_graph: list[tuple[float, int, str]]

    graph_max_y: str
    graph_min_x: float
    graph_max_x: float
    price_prefix: str
    price_suffix: str


class Activity(TypedDict):
    type: str
    quantity: str
    price: str
    time: int
    avatar_buyer: str
    avatar_medium_buyer: str
    persona_buyer: str
    avatar_seller: str
    avatar_medium_seller: str
    persona_seller: str


class ItemOrdersActivity(TypedDict):
    success: SUCCESS
    activity: list[Activity]
    timestamp: int


class PriceOverview(TypedDict):
    success: SUCCESS
    lowest_price: str
    volume: str
    median_price: str
