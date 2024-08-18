"""Typed dicts for responses and methods."""

from typing import TypedDict, Literal


class SellOrderTableData(TypedDict):
    price: str
    price_with_fee: str
    quantity: str


class BuyOrderTableData(TypedDict):
    price: str
    quantity: str


class ItemOrdersHistogramData(TypedDict):
    success: int
    sell_order_count: str
    sell_order_price: str
    sell_order_table: list[SellOrderTableData]
    buy_order_count: str
    buy_order_price: str
    buy_order_table: list[BuyOrderTableData]
    highest_buy_order: str
    lowest_sell_order: str

    # actually there is a lists, but tuple typing have fixed values
    buy_order_graph: list[tuple[float, int, str]]
    sell_order_graph: list[tuple[float, int, str]]

    graph_max_y: int
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
    success: int
    activity: list[Activity]
    timestamp: int


class PriceOverview(TypedDict):
    success: int
    lowest_price: str
    volume: str
    median_price: str


class TradeOffersSummary(TypedDict):
    pending_received_count: int
    new_received_count: int
    updated_received_count: int
    historical_received_count: int
    pending_sent_count: int
    newly_accepted_sent_count: int
    updated_sent_count: int
    historical_sent_count: int
    escrow_received_count: int
    escrow_sent_count: int


class WalletInfo(TypedDict):
    wallet_currency: int
    wallet_country: str
    wallet_state: str
    wallet_fee: str
    wallet_fee_minimum: str
    wallet_fee_percent: str
    wallet_publisher_fee_percent_default: str
    wallet_fee_base: str
    wallet_balance: str
    wallet_delayed_balance: str
    wallet_max_balance: str
    wallet_trade_max_balance: str
    success: int
    rwgrsn: int


class UserWallet(TypedDict):
    amount: str  # int
    currency: str


class FundWalletInfo(TypedDict):
    """From `https://store.steampowered.com/api/getfundwalletinfo`"""

    success: int
    currency: str
    country_code: str
    alternate_min_amount: bool
    amounts: list[int]
    related_trans_type: bool
    related_trainsid: bool
    user_wallet: UserWallet


class JWTToken(TypedDict):
    iss: str
    sub: str  # steam id64
    aud: list[str]
    exp: int
    nbf: int
    iat: int
    jti: str
    oat: int
    per: int
    ip_subject: str
    ip_confirmer: str


class LocationData(TypedDict):
    locCity: str
    locCityCode: int
    locCountry: str
    locCountryCode: str
    locState: str
    locStateCode: str


class ProfilePrivacySettings(TypedDict):
    PrivacyFriendsList: int
    PrivacyInventory: int
    PrivacyInventoryGifts: int
    PrivacyOwnedGames: int
    PrivacyPlaytime: int
    PrivacyProfile: int


class ProfilePrivacy(TypedDict):
    PrivacySettings: ProfilePrivacySettings
    eCommentPermission: int


class ProfilePreferences(TypedDict):
    hide_profile_awards: int


class ProfileData(TypedDict):
    strPersonaName: str
    strCustomURL: str
    strRealName: str
    strSummary: str
    strAvatarHash: str
    rtPersonaNameBannedUntil: str
    rtProfileSummaryBannedUntil: str
    rtAvatarBannedUntil: str
    LocationData: LocationData
    # ActiveTheme
    ProfilePreferences: ProfilePreferences
    # rgAvailableThemes
    # rgGoldenProfileData
    Privacy: ProfilePrivacy
