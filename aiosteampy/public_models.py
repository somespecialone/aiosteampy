from typing import TypedDict


class SellOrderTable(TypedDict):
    price: str
    price_with_fee: str
    quantity: str


class BuyOrderTable(TypedDict):
    price: str
    quantity: str


class ItemOrdersHistogram(TypedDict):
    success: int
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
