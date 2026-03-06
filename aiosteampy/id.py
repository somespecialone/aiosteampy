"""Representation of `SteamID`."""

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
    """Steam universe types."""

    INVALID = 0
    PUBLIC = 1
    BETA = 2
    INTERNAL = 3
    DEV = 4


class AccountType(IntEnum):
    """Steam account types."""

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
    """Steam instance types."""

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
    __slots__ = ("_universe", "_type", "_instance", "_account_id", "_id64")

    def __init__(self, input_id: str | int | None = None):
        """
        Represents a `Steam ID` and provides methods for parsing and rendering
        in various formats (`Steam2`, `Steam3`, 32-bit, 64-bit).

        :param input_id: Can be a 32/64-bit integer or string representation, a `Steam2` format string ("STEAM_X:Y:Z"),
            or a `Steam3` format string ("[U:X:Y]"). If None, creates blank (invalid) ID.
        """

        self._universe = Universe.INVALID
        self._type = AccountType.INVALID
        self._instance = Instance.ALL
        self._account_id = 0
        self._id64 = 0

        if not input_id:
            return

        elif isinstance(input_id, int) or (isinstance(input_id, str) and input_id.isdigit()):  # numeric formats
            input_id = int(input_id)

            if input_id < 0:
                raise ValueError("ID cannot be negative")

            elif input_id < 2**32:  # 32-bit account ID, public only
                self._universe = Universe.PUBLIC
                self._type = AccountType.INDIVIDUAL
                self._instance = Instance.DESKTOP
                self._account_id = input_id

            elif input_id < 2**64:  # and 64-bit
                self._universe = Universe((input_id >> 56) & 0xFF)
                self._type = AccountType((input_id >> 52) & 0xF)
                self._instance = Instance((input_id >> 32) & ACCOUNT_INSTANCE_MASK)
                self._account_id = input_id & ACCOUNT_ID_MASK

            else:
                raise ValueError("ID is too large")

        elif isinstance(input_id, str):  # Steam2/3 formats
            # Handle Steam2 format: STEAM_X:Y:Z
            if match := STEAM_2_FORMAT_RE.match(input_id):
                universe_str, mod, account_id = match.groups()

                universe = int(universe_str)
                self._universe = Universe(universe or 1)  # 0 -> 1
                self._type = AccountType.INDIVIDUAL
                self._instance = Instance.DESKTOP
                self._account_id = (int(account_id) * 2) + int(mod)

            # Handle Steam3 format: [T:U:A] or [T:U:A:I]
            elif match := STEAM_3_FORMAT_RE.match(input_id):
                type_char, universe, account_id, instance = match.groups()

                self._universe = Universe(int(universe))
                self._account_id = int(account_id)

                if instance:
                    self._instance = Instance(int(instance))

                # Handle special type characters
                if type_char == "U":
                    self._type = AccountType.INDIVIDUAL
                    if instance is None:
                        self._instance = Instance.DESKTOP
                elif type_char == "c":
                    self._instance |= CHAT_INSTANCE_FLAG_CLAN
                    self._type = AccountType.CHAT
                elif type_char == "L":
                    self._instance |= CHAT_INSTANCE_FLAG_LOBBY
                    self._type = AccountType.CHAT
                else:
                    for account_type, char in TYPE_CHARS.items():
                        if char == type_char:
                            self._type = account_type
                    else:
                        self._type = AccountType.INVALID

            else:
                raise ValueError(f'Unknown SteamID input format: "{input_id}"')

        else:
            raise ValueError(f'Unknown SteamID input type: "{type(input_id)}"')

        self._id64 = (self._universe << 56) | (self._type << 52) | (self._instance << 32) | self._account_id

    @property
    def universe(self) -> Universe:
        return self._universe

    @property
    def type(self) -> AccountType:
        return self._type

    @property
    def instance(self) -> Instance:
        return self._instance

    @property
    def account_id(self) -> int:
        return self._account_id

    @property
    def valid(self) -> bool:
        """
        Check whether this ``SteamID`` is valid according to `Steam's` rules.

        .. note:: Does not check whether the account actually exists.
        """

        if self._type <= AccountType.INVALID or self._type > AccountType.ANON_USER:
            return False

        if self._universe <= Universe.INVALID or self._universe > Universe.DEV:
            return False

        if self._type == AccountType.INDIVIDUAL:
            if self._account_id == 0 or self._instance > Instance.WEB:
                return False

        if self._type == AccountType.CLAN:
            if self._account_id == 0 or self._instance != Instance.ALL:
                return False

        if self._type == AccountType.GAMESERVER and self._account_id == 0:
            return False

        return True

    @property
    def is_individual(self) -> bool:
        """
        Check if this is a valid individual user ID in the public universe with a desktop instance.

        **This is what most people think of what is SteamID**.

        .. note:: Does not check whether the account actually exists.
        """

        return (
            self._universe == Universe.PUBLIC
            and self._type == AccountType.INDIVIDUAL
            and self._instance == Instance.DESKTOP
            and self.valid
        )

    @property
    def is_group_chat(self) -> bool:
        """If represents a legacy group chat."""

        return self._type == AccountType.CHAT and bool(self._instance & CHAT_INSTANCE_FLAG_CLAN)

    @property
    def is_lobby(self) -> bool:
        """If represents a game lobby."""

        return self._type == AccountType.CHAT and bool(
            self._instance & (CHAT_INSTANCE_FLAG_LOBBY | CHAT_INSTANCE_FLAG_MMS_LOBBY)
        )

    @property
    def steam2(self) -> str | None:
        """`Steam2` format representation (e.g., "STEAM_1:0:23071901"). ``None`` for non-individual `IDs`."""

        if self._type == AccountType.INDIVIDUAL:
            return f"STEAM_{self._universe}:{self._account_id & 1}:{self._account_id // 2}"

    @property
    def steam3(self) -> str:
        """`Steam3` format representation (e.g., "[U:1:46143802]")."""

        type_char = TYPE_CHARS.get(self._type, "i")

        if self._instance & CHAT_INSTANCE_FLAG_CLAN:
            type_char = "c"
        elif self._instance & CHAT_INSTANCE_FLAG_LOBBY:
            type_char = "L"

        should_render_instance = (
            self._type == AccountType.ANON_GAMESERVER
            or self._type == AccountType.MULTISEAT
            or (self._type == AccountType.INDIVIDUAL and self._instance != Instance.DESKTOP)
        )

        instance_str = f":{self._instance}" if should_render_instance else ""
        return f"[{type_char}:{self._universe}:{self._account_id}{instance_str}]"

    @property
    def id32(self) -> int:
        """32-bit representation. Alias to ``account_id``."""
        return self._account_id

    @property
    def id64(self) -> int:
        """64-bit representation."""
        return self._id64

    def __str__(self):
        return str(self._id64)

    def __int__(self):
        return self._id64

    def __repr__(self):
        return f"{self.__class__.__name__}({self._id64})"

    def __eq__(self, other):
        return isinstance(other, SteamID) and self._id64 == other._id64

    def __hash__(self):
        return self._id64

    def __bool__(self):
        return self.valid
