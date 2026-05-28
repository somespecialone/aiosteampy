"""`CS2` app specific context."""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, Literal, NamedTuple, Self

import betterproto2

from .app import App
from .components.market.query import ListingsQuery

if TYPE_CHECKING:  # break circle import
    from .components.market import ListingItem, MarketListingItem
    from .components.market.models import ListingItemAccessory
    from .components.trade import TradeOfferItem
    from .econ import AssetAccessory, EconItem, ItemDescription


INSPECT_LINK_BASE = "steam://run/730//+csgo_econ_action_preview%20"
# search sticker and charm data
CS2_APPLICABLE_DATA_RE = re.compile(r'<img\s+[^>]*src="([^"]*)"[^>]*title="([^"]*)"[^>]*>')


# https://steamapi.xpaw.me/IEconService#GetAssetPropertySchema
class AssetPropertyId(IntEnum):
    PATTERN_TEMPLATE = 1  # seed
    WEAR_RATING = 2  # float value
    CHARM_TEMPLATE = 3  # charm seed(pattern)
    STICKER_SCRAPE_LEVEL = 4  # sticker wear
    NAME_TAG = 5
    ITEM_CERTIFICATE = 6  # now we know what this is
    """Inspect key of item."""
    FINISH_CATALOG = 7

    @classmethod
    def get(cls, value: int) -> Self | None:
        try:
            return cls(value)
        except KeyError:
            return None


class ItemAccessoryMeta(NamedTuple):
    name: str  # title
    icon: str


# these can be used as market search filters
class ItemExterior(StrEnum):
    FactoryNew = "Factory New"
    MinimalWear = "Minimal Wear"
    FieldTested = "Field-Tested"
    WellWorn = "Well-Worn"
    BattleScarred = "Battle-Scarred"
    NotPainted = "Not Painted"

    @classmethod
    def from_description(cls, description: str) -> Self:
        return cls(description.split(": ")[1])  # Exterior: <wear>


class DescriptionDescriptionName(StrEnum):  # lol
    Sticker = "sticker_info"
    Charm = "keychain_info"
    Collection = "itemset_name"
    Exterior = "exterior_wear"
    StattrakScore = "stattrak_score"
    # Description = "description"  # not meaningful

    @classmethod
    def get(cls, value: str) -> Self | None:
        try:
            return cls(value)
        except ValueError:
            return None


@dataclass(slots=True)
class DescriptionContext:
    """Representation of `CS2` specific ``ItemDescription`` data."""

    # from descriptions
    stickers: tuple[ItemAccessoryMeta, ...]
    """List of `stickers` metadata."""
    charm: ItemAccessoryMeta | None
    """`Charm` metadata."""
    collection: str | None
    exterior: ItemExterior | None

    stattrak_score: int | None

    # fields from below will be not as much helpful as we can await, so implementing them is unnecessary
    # inventory only (from tags)
    # type: ...
    # quality: ...
    # rarity: ...

    # weapon: Weapon
    # sticker: StickerCategory, Tournament, TournamentTeam, StickerCapsule, ProPlayer

    @classmethod
    def from_description(cls, descr: "ItemDescription") -> Self:
        if descr.app is not App.CS2:
            raise ValueError("Passed description belongs to other app than CS2")

        stickers = ()
        charm = None
        collection = None
        exterior = None
        stattrak_score = None
        for d in descr.descriptions:
            match DescriptionDescriptionName.get(d.name):
                case DescriptionDescriptionName.Sticker:
                    stickers = tuple(ItemAccessoryMeta(t, s) for s, t in CS2_APPLICABLE_DATA_RE.findall(d.value))
                case DescriptionDescriptionName.Charm:
                    search = CS2_APPLICABLE_DATA_RE.search(d.value)
                    charm = ItemAccessoryMeta(name=search.group(1), icon=search.group(2))
                case DescriptionDescriptionName.Collection:
                    collection = d.value
                case DescriptionDescriptionName.Exterior:  # safe to get from descriptions in any case
                    exterior = ItemExterior.from_description(d.value)
                case DescriptionDescriptionName.StattrakScore:
                    stattrak_score = int(d.value.split(": ")[1])  # let's hope that this option is lang safe

        return cls(stickers, charm, collection, exterior, stattrak_score)


@dataclass(slots=True)
class ItemAccessory:
    class_id: int
    meta: ItemAccessoryMeta
    description: "ItemDescription | None"


@dataclass(slots=True)
class Sticker(ItemAccessory):
    wear: float


@dataclass(slots=True)
class Charm(ItemAccessory):
    pattern: int | None


# https://github.com/SteamTracking/Protobufs/blob/e0029427a75d9247e8d15b11d812cf6c00519304/csgo/cstrike15_gcmessages.proto#L915
@dataclass(repr=False)
class CEconItemPreviewDataBlock(betterproto2.Message):
    accountid: "int" = betterproto2.field(1, betterproto2.TYPE_UINT32)
    itemid: "int" = betterproto2.field(2, betterproto2.TYPE_UINT64)
    defindex: "int" = betterproto2.field(3, betterproto2.TYPE_UINT32)
    paintindex: "int" = betterproto2.field(4, betterproto2.TYPE_UINT32)
    rarity: "int" = betterproto2.field(5, betterproto2.TYPE_UINT32)
    quality: "int" = betterproto2.field(6, betterproto2.TYPE_UINT32)
    paintwear: "int" = betterproto2.field(7, betterproto2.TYPE_UINT32)
    paintseed: "int" = betterproto2.field(8, betterproto2.TYPE_UINT32)
    killeaterscoretype: "int" = betterproto2.field(9, betterproto2.TYPE_UINT32)
    killeatervalue: "int" = betterproto2.field(10, betterproto2.TYPE_UINT32)
    customname: "str" = betterproto2.field(11, betterproto2.TYPE_STRING)
    stickers: "list[CEconItemPreviewDataBlockSticker]" = betterproto2.field(
        12, betterproto2.TYPE_MESSAGE, repeated=True
    )
    inventory: "int" = betterproto2.field(13, betterproto2.TYPE_UINT32)
    origin: "int" = betterproto2.field(14, betterproto2.TYPE_UINT32)
    questid: "int" = betterproto2.field(15, betterproto2.TYPE_UINT32)
    dropreason: "int" = betterproto2.field(16, betterproto2.TYPE_UINT32)
    musicindex: "int" = betterproto2.field(17, betterproto2.TYPE_UINT32)
    entindex: "int" = betterproto2.field(18, betterproto2.TYPE_INT32)
    petindex: "int" = betterproto2.field(19, betterproto2.TYPE_UINT32)
    keychains: "list[CEconItemPreviewDataBlockSticker]" = betterproto2.field(
        20, betterproto2.TYPE_MESSAGE, repeated=True
    )
    style: "int" = betterproto2.field(21, betterproto2.TYPE_UINT32)
    variations: "list[CEconItemPreviewDataBlockSticker]" = betterproto2.field(
        22, betterproto2.TYPE_MESSAGE, repeated=True
    )
    upgrade_level: "int" = betterproto2.field(23, betterproto2.TYPE_UINT32)

    @classmethod
    def from_certificate(cls, certificate: str) -> Self:
        """Parse `item certificate` and create an instance."""

        buffer = bytearray.fromhex(certificate)

        if buffer[0] != 0:  # unmask
            mask = buffer[0]
            for i in range(1, len(buffer) - 3):
                buffer[i] ^= mask

        return cls.parse(buffer[1:-4])


@dataclass(eq=False, repr=False)
class CEconItemPreviewDataBlockSticker(betterproto2.Message):
    slot: "int" = betterproto2.field(1, betterproto2.TYPE_UINT32)
    sticker_id: "int" = betterproto2.field(2, betterproto2.TYPE_UINT32)
    wear: "float" = betterproto2.field(3, betterproto2.TYPE_FLOAT)
    scale: "float" = betterproto2.field(4, betterproto2.TYPE_FLOAT)
    rotation: "float" = betterproto2.field(5, betterproto2.TYPE_FLOAT)
    tint_id: "int" = betterproto2.field(6, betterproto2.TYPE_UINT32)
    offset_x: "float" = betterproto2.field(7, betterproto2.TYPE_FLOAT)
    offset_y: "float" = betterproto2.field(8, betterproto2.TYPE_FLOAT)
    offset_z: "float" = betterproto2.field(9, betterproto2.TYPE_FLOAT)
    pattern: "int" = betterproto2.field(10, betterproto2.TYPE_UINT32)
    highlight_reel: "int" = betterproto2.field(11, betterproto2.TYPE_UINT32)
    wrapped_sticker: "int" = betterproto2.field(12, betterproto2.TYPE_UINT32)


# can this and preview(inspect data) be merged into something unified?
@dataclass(slots=True)
class ItemContext:
    """Representation of `CS2` specific ``EconItem`` data."""

    description_ctx: DescriptionContext

    # absent in market listings data
    stickers: tuple[Sticker, ...]
    charm: Charm | None

    certificate: str | None
    """Encoded `inspect` preview data."""
    wear_rating: float | None
    """Paint wear rating, known as `float` or `floatvalue`."""
    pattern_template: int | None
    name_tag: str | None

    _inspect_data: CEconItemPreviewDataBlock | None = None

    @property
    def inspect_link(self) -> str | None:
        """`Inspect in Game...` link."""
        return (INSPECT_LINK_BASE + self.certificate) if self.certificate else None

    @property
    def inspect_data(self) -> CEconItemPreviewDataBlock | None:
        """Item preview data."""

        if self.certificate:
            if self._inspect_data is None:
                self._inspect_data = CEconItemPreviewDataBlock.from_certificate(self.certificate)

            return self._inspect_data

    @staticmethod
    def _create_sticker(sticker_meta: ItemAccessoryMeta, accessory: "AssetAccessory | ListingItemAccessory") -> Sticker:
        w_prop = accessory.parent_relationship_properties[0]
        assert AssetPropertyId(w_prop.id) is AssetPropertyId.STICKER_SCRAPE_LEVEL

        # float will round to 16 digits from original 18
        return Sticker(
            class_id=accessory.class_id,
            meta=sticker_meta,
            wear=float(w_prop.value),
            description=getattr(accessory, "description", None),
        )

    @classmethod
    def from_item(cls, item: "EconItem | MarketListingItem | TradeOfferItem| ListingItem") -> Self:
        if item.description.app is not App.CS2:
            raise ValueError("Passed item belongs to other app than CS2.")

        descr_ctx = item.description.cs2

        stickers = ()
        if item.accessories and descr_ctx.stickers:
            stickers = tuple(cls._create_sticker(m, a) for m, a in zip(descr_ctx.stickers, item.accessories))

        charm = None
        if item.accessories and descr_ctx.charm is not None:
            pattern = None
            accs = item.accessories[-1]
            if accs.standalone_properties:
                assert accs.standalone_properties
                p_prop = accs.standalone_properties[0]
                assert AssetPropertyId(p_prop.id) is AssetPropertyId.CHARM_TEMPLATE

                pattern = int(p_prop.value)

            charm = Charm(
                class_id=accs.class_id,
                meta=descr_ctx.charm,
                pattern=pattern,
                description=getattr(accs, "description", None),
            )

        inspect_id = None
        wear_rating = None
        pattern = None
        name_tag = None
        for prop in item.properties:
            match AssetPropertyId.get(prop.id):
                case AssetPropertyId.ITEM_CERTIFICATE:
                    inspect_id = prop.value
                case AssetPropertyId.WEAR_RATING:
                    wear_rating = float(prop.value)  # will round to 16 digits from original 18
                case AssetPropertyId.PATTERN_TEMPLATE:
                    pattern = int(prop.value)
                case AssetPropertyId.NAME_TAG:
                    name_tag = prop.value

        return cls(descr_ctx, stickers, charm, inspect_id, wear_rating, pattern, name_tag)


TExteriors = Literal["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred", "Not Painted"]

TQualities = Literal[
    "Normal",
    "Souvenir",
    "StatTrak™",
    "★",  # unused
    "★ StatTrak™",  # simple stattrak can be used instead
    "Highlight",  # ?
    "Customized",  # ?
]

TTypes = Literal[
    "SMG",
    "Pistol",
    "Rifle",
    "Sniper Rifle",
    "Shotgun",
    "Machinegun",
    "Charm",
    "Equipment",
    "Knife",
    "Agent",
    "Container",
    "Sticker",
    "Gloves",
    "Graffiti",
    "Music Kit",
    "Patch",
    "Collectible",
    "Pass",
    "Key",
    "Gift",
    "Tag",
    "Tool",
]

TWeapons = Literal[
    "MP9",
    "PP-Bizon",
    "SSG 08",
    "P90",
    "P250",
    "SCAR-20",
    "Nova",
    "MAC-10",
    "UMP-45",
    "Tec-9",
    "G3SG1",
    "MP5-SD",
    "MAG-7",
    "SG 553",
    "Sawed-Off",
    "MP7",
    "Dual Berettas",
    "R8 Revolver",
    "FAMAS",
    "AUG",
    "Five-SeveN",
    "AK-47",
    "Galil AR",
    "M249",
    "CZ75-Auto",
    "XM1014",
    "M4A1-S",
    "Negev",
    "Desert Eagle",
    "USP-S",
    "Zeus x27",
    "M4A4",
    "Glock-18",
    "AWP",
    "P2000",
    "Kukri Knife",
    "Shadow Daggers",
    "Bowie Knife",
    "Falchion Knife",
    "Survival Knife",
    "Huntsman Knife",
    "Paracord Knife",
    "Navaja Knife",
    "Gut Knife",
    "Nomad Knife",
    "Skeleton Knife",
    "Ursus Knife",
    "Bayonet",
    "Flip Knife",
    "Butterfly Knife",
    "Stiletto Knife",
    "Talon Knife",
    "Classic Knife",
    "M9 Bayonet",
    "Karambit",
]

TStickerTypes = Literal["Player Autograph", "Team Logo", "Tournament"]

# localized: value
TAGS_MAP = {
    "AK-47": "weapon_ak47",
    "AUG": "weapon_aug",
    "AWP": "weapon_awp",
    "Agent": "Type_CustomPlayer",
    "Battle-Scarred": "WearCategory4",
    "Bayonet": "weapon_bayonet",
    "Bowie Knife": "weapon_knife_survival_bowie",
    "Butterfly Knife": "weapon_knife_butterfly",
    "CZ75-Auto": "weapon_cz75a",
    "Charm": "CSGO_Tool_Keychain",
    "Classic Knife": "weapon_knife_css",
    "Collectible": "CSGO_Type_Collectible",
    "Container": "CSGO_Type_WeaponCase",
    "Customized": "customized",
    "Desert Eagle": "weapon_deagle",
    "Dual Berettas": "weapon_elite",
    "Equipment": "CSGO_Type_Equipment",
    "FAMAS": "weapon_famas",
    "Factory New": "WearCategory0",
    "Falchion Knife": "weapon_knife_falchion",
    "Field-Tested": "WearCategory2",
    "Five-SeveN": "weapon_fiveseven",
    "Flip Knife": "weapon_knife_flip",
    "G3SG1": "weapon_g3sg1",
    "Galil AR": "weapon_galilar",
    "Gift": "CSGO_Tool_GiftTag",
    "Glock-18": "weapon_glock",
    "Gloves": "Type_Hands",
    "Graffiti": "CSGO_Type_Spray",
    "Gut Knife": "weapon_knife_gut",
    "Highlight": "highlight",
    "Huntsman Knife": "weapon_knife_tactical",
    "Karambit": "weapon_knife_karambit",
    "Key": "CSGO_Tool_WeaponCase_KeyTag",
    "Knife": "CSGO_Type_Knife",
    "Kukri Knife": "weapon_knife_kukri",
    "M249": "weapon_m249",
    "M4A1-S": "weapon_m4a1_silencer",
    "M4A4": "weapon_m4a1",
    "M9 Bayonet": "weapon_knife_m9_bayonet",
    "MAC-10": "weapon_mac10",
    "MAG-7": "weapon_mag7",
    "MP5-SD": "weapon_mp5sd",
    "MP7": "weapon_mp7",
    "MP9": "weapon_mp9",
    "Machinegun": "CSGO_Type_Machinegun",
    "Minimal Wear": "WearCategory1",
    "Music Kit": "CSGO_Type_MusicKit",
    "Navaja Knife": "weapon_knife_gypsy_jackknife",
    "Negev": "weapon_negev",
    "Nomad Knife": "weapon_knife_outdoor",
    "Normal": "normal",
    "Not Painted": "WearCategoryNA",
    "Nova": "weapon_nova",
    "P2000": "weapon_hkp2000",
    "P250": "weapon_p250",
    "P90": "weapon_p90",
    "PP-Bizon": "weapon_bizon",
    "Paracord Knife": "weapon_knife_cord",
    "Pass": "CSGO_Type_Ticket",
    "Patch": "CSGO_Tool_Patch",
    "Pistol": "CSGO_Type_Pistol",
    "R8 Revolver": "weapon_revolver",
    "Rifle": "CSGO_Type_Rifle",
    "SCAR-20": "weapon_scar20",
    "SG 553": "weapon_sg556",
    "SMG": "CSGO_Type_SMG",
    "SSG 08": "weapon_ssg08",
    "Sawed-Off": "weapon_sawedoff",
    "Shadow Daggers": "weapon_knife_push",
    "Shotgun": "CSGO_Type_Shotgun",
    "Skeleton Knife": "weapon_knife_skeleton",
    "Sniper Rifle": "CSGO_Type_SniperRifle",
    "Souvenir": "tournament",
    "StatTrak™": "strange",
    "Sticker": "CSGO_Tool_Sticker",
    "Stiletto Knife": "weapon_knife_stiletto",
    "Survival Knife": "weapon_knife_canis",
    "Tag": "CSGO_Tool_Name_TagTag",
    "Talon Knife": "weapon_knife_widowmaker",
    "Tec-9": "weapon_tec9",
    "Tool": "CSGO_Type_Tool",
    "UMP-45": "weapon_ump45",
    "USP-S": "weapon_usp_silencer",
    "Ursus Knife": "weapon_knife_ursus",
    "Well-Worn": "WearCategory3",
    "XM1014": "weapon_xm1014",
    "Zeus x27": "weapon_taser",
    "★": "unusual",
    "★ StatTrak™": "unusual_strange",
}


@dataclass(slots=True, kw_only=True)
class CS2SearchQuery(ListingsQuery):
    """
    ``CS2`` specific query builder for `listings`,
    uses `localized` names for methods and values.
    Non-exhaustive, so does not contain every possible filter typed.

    .. note:: This builder does not prevent a wrong filters combination,
        so it is strongly advised to be vigilant.
    """

    # anyway app need to be passed in component methods
    # better to be redesigned
    app: App = field(default_factory=lambda: App.CS2)

    def _add_filters(self, facet: str, values: Iterable[str]):
        for value in values:
            self.filter(facet, TAGS_MAP[value])

    def _add_accessories(self, facet: str, values: Iterable[str]):
        for value in values:
            self.accessory(facet, value)

    def exterior(self, *values: TExteriors | ItemExterior) -> Self:
        """Add ``exterior`` filter."""
        self._add_filters("Exterior", (str(v) for v in values))
        return self

    def category(self, *values: TQualities) -> Self:
        """Add ``category`` filter."""
        self._add_filters("Quality", values)
        return self

    def type(self, *values: TTypes) -> Self:
        """Add ``type`` filter."""
        self._add_filters("Type", values)
        return self

    def weapon(self, *values: TWeapons) -> Self:
        """Add ``weapon`` filter."""
        self._add_filters("Weapon", values)
        return self

    def sticker_type(self, *values: TStickerTypes) -> Self:
        """Add ``sticker_type`` filter."""
        self._add_filters("StickerCategory", values)
        return self

    def sticker(self, *values: str) -> Self:
        """Add attached ``sticker`` to item as filter. Value must be `sticker` full name(market hash name)."""
        self._add_accessories(TAGS_MAP["Sticker"], values)
        return self

    def charm(self, *values: str) -> Self:
        """Add attached ``charm`` to item as filter. Value must be `keychain` full name(market hash name)."""
        self._add_accessories(TAGS_MAP["Charm"], values)
        return self

    def wear_rating(self, min_: float = 0, max_: float = 1) -> Self:
        """Set `wear rating (ala floatvalue)` range as filter."""
        self.property(2, float_min=min_, float_max=max_)
        return self

    def pattern(self, min_: int = 0, max_: int = 1000) -> Self:
        """Set `pattern template (paint seed)` range as filter."""
        self.property(1, int_min=min_, int_max=max_)  # browser sends values as string, hah
        return self
