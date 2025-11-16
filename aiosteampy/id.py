import re

from enum import IntEnum

__all__ = ("Universe", "AccountType", "Instance", "SteamID")


STEAM_2_FORMAT_RE = re.compile(r"^STEAM_([0-5]):([0-1]):(\d+)$")
STEAM_3_FORMAT_RE = re.compile(r"^\[([a-zA-Z]):([0-5]):(\d+)(?::(\d+))?]$")

ACCOUNT_ID_MASK = 0xFFFFFFFF
ACCOUNT_INSTANCE_MASK = 0xFFFFF

# Chat instance flags
CHAT_INSTANCE_FLAG_CLAN = (ACCOUNT_INSTANCE_MASK + 1) >> 1
CHAT_INSTANCE_FLAG_LOBBY = (ACCOUNT_INSTANCE_MASK + 1) >> 2
CHAT_INSTANCE_FLAG_MMS_LOBBY = (ACCOUNT_INSTANCE_MASK + 1) >> 3


class Universe(IntEnum):
    """Steam universe types"""

    INVALID = 0
    PUBLIC = 1
    BETA = 2
    INTERNAL = 3
    DEV = 4


class AccountType(IntEnum):
    """Steam account types"""

    INVALID = 0
    INDIVIDUAL = 1
    MULTISEAT = 2
    GAMESERVER = 3
    ANON_GAMESERVER = 4
    PENDING = 5
    CONTENT_SERVER = 6
    CLAN = 7
    CHAT = 8
    P2P_SUPER_SEEDER = 9
    ANON_USER = 10


class Instance(IntEnum):
    """Steam instance types"""

    ALL = 0
    DESKTOP = 1
    CONSOLE = 2
    WEB = 4


# Type character mappings
TYPE_CHARS = {
    AccountType.INVALID: "I",
    AccountType.INDIVIDUAL: "U",
    AccountType.MULTISEAT: "M",
    AccountType.GAMESERVER: "G",
    AccountType.ANON_GAMESERVER: "A",
    AccountType.PENDING: "P",
    AccountType.CONTENT_SERVER: "C",
    AccountType.CLAN: "g",
    AccountType.CHAT: "T",
    AccountType.ANON_USER: "a",
}


class SteamID:
    __slots__ = ("universe", "type", "instance", "account_id")

    universe: Universe
    type: AccountType
    instance: Instance

    def __init__(self, input_id: str | int | None = None):
        """
        Represents a Steam ID and provides methods for parsing and rendering
        in various formats (Steam2, Steam3, 32-bit, 64-bit)

        :param input_id: Can be a 32/64-bit integer or string representation, a Steam2 format string (STEAM_X:Y:Z),
            or a Steam3 format string ([U:X:Y]). If None, creates blank (invalid) ID
        """

        self.universe = Universe.INVALID
        self.type = AccountType.INVALID
        self.instance = Instance.ALL
        self.account_id = 0

        if input_id is None:
            return

        if isinstance(input_id, int) or input_id.isdigit():  # numeric formats
            input_id = int(input_id)

            if input_id < 0:
                raise ValueError("ID cannot be negative")

            elif input_id < 2**32:  # 32-bit account ID, public only
                self._parse_32bit(input_id)

            elif input_id < 2**64:  # and 64-bit
                self._parse_64bit(input_id)

            else:
                raise ValueError("ID is too large")

        elif isinstance(input_id, str):  # Steam2/3 formats
            # Handle Steam2 format: STEAM_X:Y:Z
            if steam2_match := STEAM_2_FORMAT_RE.match(input_id):
                self._parse_steam2(steam2_match)

            # Handle Steam3 format: [T:U:A] or [T:U:A:I]
            elif steam3_match := STEAM_3_FORMAT_RE.match(input_id):
                self._parse_steam3(steam3_match)

            else:
                raise ValueError(f'Unknown SteamID input format: "{input_id}"')

    def _parse_32bit(self, account_id: int):
        self.universe = Universe.PUBLIC
        self.type = AccountType.INDIVIDUAL
        self.instance = Instance.DESKTOP
        self.account_id = account_id

    def _parse_64bit(self, id64: int):
        self.universe = Universe((id64 >> 56) & 0xFF)
        self.type = AccountType((id64 >> 52) & 0xF)
        self.instance = Instance((id64 >> 32) & ACCOUNT_INSTANCE_MASK)
        self.account_id = id64 & ACCOUNT_ID_MASK

    def _parse_steam2(self, match: re.Match):
        universe_str, mod, account_id = match.groups()

        universe = int(universe_str)
        self.universe = Universe(universe or 1)  # 0 -> 1
        self.type = AccountType.INDIVIDUAL
        self.instance = Instance.DESKTOP
        self.account_id = (int(account_id) * 2) + int(mod)

    def _parse_steam3(self, match: re.Match):
        type_char, universe, account_id, instance = match.groups()

        self.universe = Universe(int(universe))
        self.account_id = int(account_id)

        if instance:
            self.instance = Instance(int(instance))

        # Handle special type characters
        if type_char == "U":
            self.type = AccountType.INDIVIDUAL
            if instance is None:
                self.instance = Instance.DESKTOP
        elif type_char == "c":
            self.instance |= CHAT_INSTANCE_FLAG_CLAN
            self.type = AccountType.CHAT
        elif type_char == "L":
            self.instance |= CHAT_INSTANCE_FLAG_LOBBY
            self.type = AccountType.CHAT
        else:
            for account_type, char in TYPE_CHARS.items():
                if char == type_char:
                    self.type = account_type
            else:
                self.type = AccountType.INVALID

    def is_valid(self) -> bool:
        """
        Check whether this SteamID is valid according to Steam's rules

        .. note:: Does not check whether the account actually exists
        """

        if self.type <= AccountType.INVALID or self.type > AccountType.ANON_USER:
            return False

        if self.universe <= Universe.INVALID or self.universe > Universe.DEV:
            return False

        if self.type == AccountType.INDIVIDUAL:
            if self.account_id == 0 or self.instance > Instance.WEB:
                return False

        if self.type == AccountType.CLAN:
            if self.account_id == 0 or self.instance != Instance.ALL:
                return False

        if self.type == AccountType.GAMESERVER and self.account_id == 0:
            return False

        return True

    def is_individual(self) -> bool:
        """
        Check if this is a valid individual user ID in the public universe with a desktop instance.
        This is what most people think of when they think of a SteamID

        .. note:: Does not check whether the account actually exists
        """

        return (
            self.universe == Universe.PUBLIC
            and self.type == AccountType.INDIVIDUAL
            and self.instance == Instance.DESKTOP
            and self.is_valid()
        )

    def is_group_chat(self) -> bool:
        """Check if this ID represents a legacy group chat"""

        return self.type == AccountType.CHAT and bool(self.instance & CHAT_INSTANCE_FLAG_CLAN)

    def is_lobby(self) -> bool:
        """Check if this ID represents a game lobby"""

        return self.type == AccountType.CHAT and bool(
            self.instance & (CHAT_INSTANCE_FLAG_LOBBY | CHAT_INSTANCE_FLAG_MMS_LOBBY)
        )

    @property
    def steam2(self) -> str:
        """
        ID in the newer Steam2 format (e.g., "STEAM_1:0:23071901")

        .. note:: Available only for individual ID
        """

        if self.type != AccountType.INDIVIDUAL:
            raise ValueError("Can't get Steam2 rendered ID for non-individual Steam ID")

        return f"STEAM_{self.universe}:{self.account_id & 1}:{self.account_id // 2}"

    @property
    def steam3(self) -> str:
        """ID in Steam3 format (e.g., "[U:1:46143802]")"""

        type_char = TYPE_CHARS.get(self.type, "i")

        if self.instance & CHAT_INSTANCE_FLAG_CLAN:
            type_char = "c"
        elif self.instance & CHAT_INSTANCE_FLAG_LOBBY:
            type_char = "L"

        should_render_instance = (
            self.type == AccountType.ANON_GAMESERVER
            or self.type == AccountType.MULTISEAT
            or (self.type == AccountType.INDIVIDUAL and self.instance != Instance.DESKTOP)
        )

        instance_str = f":{self.instance}" if should_render_instance else ""
        return f"[{type_char}:{self.universe}:{self.account_id}{instance_str}]"

    @property
    def id32(self) -> int:
        """32-bit representation of this Steam ID. Alias to `account_id`"""
        return self.account_id

    @property
    def id64(self) -> int:
        """64-bit representation of this Steam ID"""
        return (self.universe << 56) | (self.type << 52) | (self.instance << 32) | self.account_id

    def __str__(self):
        return str(self.id64)

    def __int__(self):
        return self.id64

    def __repr__(self):
        return (
            f"{self.__class__.__name__}"
            f"(id64={self.id64}, "
            f"universe={self.universe!r}, "
            f"type={self.type!r}, "
            f"instance={self.instance!r}, "
            f"account_id={self.account_id})"
        )

    def __eq__(self, other):
        return isinstance(other, type(self)) and self.id64 == other.id64

    def __hash__(self):
        return hash(self.id64)

    __bool__ = is_valid
