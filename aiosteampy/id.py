"""Representation of `SteamID`."""

import re
from enum import IntEnum
from typing import Self

__all__ = ("Universe", "AccountType", "Instance", "SteamID")


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


class SteamID(int):
    """
    Represents a `Steam ID` and provides methods for rendering
    in various formats (`Steam2`, `Steam3`, 32-bit, 64-bit).

    :param _x: Can be a 32/64-bit integer or string representation, a `Steam2` format string (`STEAM_X:Y:Z`),
        or a `Steam3` format string (`[U:X:Y]`). Creates *blank (invalid) ID* in case of no input.
    """

    __slots__ = ()

    _STEAM_2_FORMAT_RE = re.compile(r"^STEAM_([0-5]):([0-1]):(\d+)$")
    _STEAM_3_FORMAT_RE = re.compile(r"^\[([a-zA-Z]):([0-5]):(\d+)(?::(\d+))?]$")

    _ACCOUNT_ID_MASK = 0xFFFFFFFF
    _ACCOUNT_INSTANCE_MASK = 0xFFFFF

    # Chat instance flags
    _CHAT_INSTANCE_FLAG_CLAN = (_ACCOUNT_INSTANCE_MASK + 1) >> 1
    _CHAT_INSTANCE_FLAG_LOBBY = (_ACCOUNT_INSTANCE_MASK + 1) >> 2
    _CHAT_INSTANCE_FLAG_MMS_LOBBY = (_ACCOUNT_INSTANCE_MASK + 1) >> 3

    # Type character mapping
    _TYPE_CHAR_INDIVIDUAL = "U"
    _TYPE_CHARS = {
        AccountType.INVALID: "I",
        AccountType.INDIVIDUAL: _TYPE_CHAR_INDIVIDUAL,
        AccountType.MULTISEAT: "M",
        AccountType.GAMESERVER: "G",
        AccountType.ANON_GAMESERVER: "A",
        AccountType.PENDING: "P",
        AccountType.CONTENT_SERVER: "C",
        AccountType.CLAN: "g",
        AccountType.CHAT: "T",
        AccountType.ANON_USER: "a",
    }

    def __new__(cls, _x: str | int = 0) -> Self:
        # all underscored due to a strange PyCharm love to inherit variables from __new__ as properties

        if isinstance(_x, cls):
            return _x
        elif not _x:
            return super().__new__(cls, 0)

        _type = AccountType.INVALID
        _instance = Instance.ALL

        if isinstance(_x, int) or (isinstance(_x, str) and _x.isdigit()):  # numeric formats
            _x = int(_x)

            if _x < 0:
                raise ValueError("ID cannot be negative")

            elif _x < 2**32:  # 32-bit account ID, public only
                _universe = Universe.PUBLIC
                _type = AccountType.INDIVIDUAL
                _instance = Instance.DESKTOP
                _account_id = _x

            elif _x < 2**64:  # input is just what we need so return early
                return super().__new__(cls, _x)

            else:
                raise ValueError("ID is too large")

        elif isinstance(_x, str):  # Steam2/3 formats
            # Handle Steam2 format: STEAM_X:Y:Z
            if match := cls._STEAM_2_FORMAT_RE.match(_x):
                _universe, _mod, _account_id = match.groups()

                _universe = Universe(int(_universe) or 1)  # 0 -> 1
                _type = AccountType.INDIVIDUAL
                _instance = Instance.DESKTOP
                _account_id = (int(_account_id) * 2) + int(_mod)

            # Handle Steam3 format: [T:U:A] or [T:U:A:I]
            elif match := cls._STEAM_3_FORMAT_RE.match(_x):
                _type_char, _universe, _account_id, _instance_raw = match.groups()

                _universe = Universe(int(_universe))
                _account_id = int(_account_id)

                # Handle special type characters
                if _type_char == cls._TYPE_CHAR_INDIVIDUAL:
                    _type = AccountType.INDIVIDUAL
                    if _instance_raw:
                        _instance = Instance(int(_instance_raw))
                    else:
                        _instance = Instance.DESKTOP

                elif _type_char == "c":
                    _instance |= cls._CHAT_INSTANCE_FLAG_CLAN
                    _type = AccountType.CHAT
                elif _type_char == "L":
                    _instance |= cls._CHAT_INSTANCE_FLAG_LOBBY
                    _type = AccountType.CHAT
                else:
                    for account_type, char in cls._TYPE_CHARS.items():
                        if _type_char == char:
                            _type = account_type

            else:
                raise ValueError(f'Unknown SteamID input format: "{_x}"')

        else:
            raise TypeError(f'Unknown SteamID input type: "{type(_x)}"')

        return super().__new__(cls, ((_universe << 56) | (_type << 52) | (_instance << 32) | _account_id))

    @property
    def universe(self) -> Universe:
        return Universe((self >> 56) & 0xFF)

    @property
    def type(self) -> AccountType:
        return AccountType((self >> 52) & 0xF)

    @property
    def instance(self) -> Instance:
        return Instance((self >> 32) & self._ACCOUNT_INSTANCE_MASK)

    @property
    def account_id(self) -> int:
        return self & self._ACCOUNT_ID_MASK

    @property
    def valid(self) -> bool:
        """
        Check whether this ``SteamID`` is valid according to `Steam's` rules.

        .. note:: Does not check whether the account actually exists.
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

    @property
    def is_individual(self) -> bool:
        """
        Check if this is a valid individual user ID in the public universe with a desktop instance.

        **This is what most people think of what is SteamID**.

        .. note:: Does not check whether the account actually exists.
        """

        return (
            self.universe == Universe.PUBLIC
            and self.type == AccountType.INDIVIDUAL
            and self.instance == Instance.DESKTOP
            and self.valid
        )

    @property
    def is_group_chat(self) -> bool:
        """If represents a legacy group chat."""
        return self.type == AccountType.CHAT and bool(self.instance & self._CHAT_INSTANCE_FLAG_CLAN)

    @property
    def is_lobby(self) -> bool:
        """If represents a game lobby."""

        return self.type == AccountType.CHAT and bool(
            self.instance & (self._CHAT_INSTANCE_FLAG_LOBBY | self._CHAT_INSTANCE_FLAG_MMS_LOBBY)
        )

    @property
    def steam2(self) -> str | None:
        """`Steam2` format representation (e.g., "STEAM_1:0:23071901"). ``None`` for non-individual `IDs`."""

        if self.type == AccountType.INDIVIDUAL:
            return f"STEAM_{self.universe}:{self.account_id & 1}:{self.account_id // 2}"

    @property
    def steam3(self) -> str:
        """`Steam3` format representation (e.g., "[U:1:46143802]")."""

        if self.instance & self._CHAT_INSTANCE_FLAG_CLAN:
            type_char = "c"
        elif self.instance & self._CHAT_INSTANCE_FLAG_LOBBY:
            type_char = "L"
        else:
            type_char = self._TYPE_CHARS.get(self.type, "i")

        should_render_instance = (
            self.type == AccountType.ANON_GAMESERVER
            or self.type == AccountType.MULTISEAT
            or (self.type == AccountType.INDIVIDUAL and self.instance != Instance.DESKTOP)
        )

        instance_str = f":{self.instance}" if should_render_instance else ""
        return f"[{type_char}:{self.universe}:{self.account_id}{instance_str}]"

    @property
    def id32(self) -> int:
        """32-bit representation. Alias to ``account_id``."""
        return self.account_id

    @property
    def id64(self) -> int:
        """64-bit representation."""
        return int(self)

    def __str__(self):
        return f"{int(self)}"

    def __repr__(self):
        return f"{self.__class__.__name__}({self})"

    def __eq__(self, value):
        if isinstance(value, SteamID):
            return int(self) == int(value)
        try:
            return self == SteamID(value)
        except (ValueError, TypeError):
            return int(self) == value

    __bool__ = valid.fget
