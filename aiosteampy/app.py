"""`Steam App` and `Context` models representation."""

from typing import ClassVar, Self

__all__ = ("App", "AppContext", "ADD_NEW_MEMBERS", "change_members_mode")


ADD_NEW_MEMBERS: bool = False
"""Boolean flag whether to add new ``App`` and ``AppContext`` members when instance created."""


def change_members_mode():
    """Change ``App`` and ``AppContext`` members adding mode to ``True`` (default is ``False``)."""

    global ADD_NEW_MEMBERS

    ADD_NEW_MEMBERS = True


class App:
    __members__: dict[int, Self] = {}

    # predefined apps
    CS2: ClassVar["App"]
    """Counter-Strike 2."""

    DOTA2: ClassVar["App"]
    H1Z1: ClassVar["App"]
    """Z1 Battle Royale."""
    RUST: ClassVar["App"]
    TF2: ClassVar["App"]
    """Team Fortress 2."""
    PUBG: ClassVar["App"]
    """PUBG: BATTLEGROUNDS."""

    STEAM: ClassVar["App"]

    __slots__ = ("_id", "_name", "_icon_hash")

    def __new__(cls, app_id: int, name: str | None = None, icon_hash: str | None = None):
        if (app := cls.__members__.get(app_id)) is not None:
            return app

        inst = super().__new__(cls)
        if ADD_NEW_MEMBERS:
            cls.__members__[app_id] = inst

        inst._id = -1  # mark as non-initialized with non-existent id for faster checks

        return inst

    def __init__(self, app_id: int, name: str | None = None, icon_hash: str | None = None):
        """
        `Steam App` representation.

        :param app_id: `Steam App` id.
        :param name: `Steam App` name.
        :param icon_hash: `Steam App` icon hash.
        """

        if self._id != -1:
            return

        self._id = app_id
        self._name = name
        self._icon_hash = icon_hash

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str | None:
        return self._name

    def with_context(self, context_id: int) -> "AppContext":
        return AppContext(self, context_id)

    @property
    def icon(self) -> str | None:
        if self._icon_hash is not None:
            return (
                f"https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/{self._id}/{self._icon_hash}.jpg"
            )

    @property
    def community(self) -> str:
        """Steam App's community page url."""
        return f"https://steamcommunity.com/app/{self._id}"

    @property
    def store(self):
        """Steam App's store page url."""
        return f"https://store.steampowered.com/app/{self._id}"

    def __eq__(self, other):
        return isinstance(other, App) and self.id == other.id

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self._id}, name='{self._name}')"

    @classmethod
    def get(cls, app_id: int) -> Self | None:
        """Get existing member."""
        return cls.__members__.get(app_id)

    @classmethod
    def add(cls, app: Self, force: bool = False):
        """Add new member regardless of ``ADD_NEW_MEMBERS`` flag."""

        if (existing := cls.get(app._id)) and not force:
            raise ValueError(f"{existing} already exists")

        cls.__members__[app._id] = app


App.CS2 = App(730, "Counter-Strike 2", "8dbc71957312bbd3baea65848b545be9eae2a355")

App.DOTA2 = App(570, "Dota 2", "0bbb630d63262dd66d2fdd0f7d37e8661a410075")
App.H1Z1 = App(433850, "Z1 Battle Royale", "aee7491abfd812e2fbb4ec3326ad5f4b85c8137a")
App.RUST = App(252490, "Rust", "820be4782639f9c4b64fa3ca7e6c26a95ae4fd1c")
App.TF2 = App(440, "Team Fortress 2", "f568912870a4684f9ec76277a1a404dda6bab213")
App.PUBG = App(578080, "PUBG: BATTLEGROUNDS", "609f27278aa70697c13bf99f32c5a0248c381f9d")

App.STEAM = App(753, "Steam", "1d0167575d746dadea7706685c0f3c01c8aeb6d8")


App.__members__.update({app.id: app for app in [App.CS2, App.DOTA2, App.H1Z1, App.RUST, App.TF2, App.PUBG, App.STEAM]})


class AppContext:
    __members__: ClassVar[dict[tuple[int, int], Self]] = {}  # app id, context id

    # predefined app+context combinations
    CS2: ClassVar["AppContext"]
    """Default `CS2` inventory."""
    CS2_PROTECTED: ClassVar["AppContext"]
    """`CS2` inventory with *trade protected* items."""

    DOTA2: ClassVar["AppContext"]
    """Default `Dota 2` inventory."""
    H1Z1: ClassVar["AppContext"]
    """Default `H1Z1` inventory."""
    RUST: ClassVar["AppContext"]
    """Default `Rust` inventory."""
    TF2: ClassVar["AppContext"]
    """Default `TF2` inventory."""
    PUBG: ClassVar["AppContext"]
    """Default `PUBG` inventory."""

    STEAM_GIFTS: ClassVar["AppContext"]
    """`Steam` inventory with `gifts`."""
    STEAM_COMMUNITY: ClassVar["AppContext"]
    """`Steam` inventory with `community` items."""
    STEAM_REWARDS: ClassVar["AppContext"]
    """`Steam` inventory with item `rewards`."""

    __slots__ = ("_app", "_context_id")

    def __new__(cls, app: App, context_id: int):
        arg_tuple = (app.id, context_id)
        if (app_ctx := cls.__members__.get(arg_tuple)) is not None:
            return app_ctx

        inst = super(AppContext, cls).__new__(cls)
        if ADD_NEW_MEMBERS:
            cls.__members__[arg_tuple] = inst

        inst._context_id = -1  # mark as non-initialized with non-existent id for faster checks

        return inst

    def __init__(self, app: App, context_id: int):
        """Representation of `App` and `Context` (sub-inventory of the app) combination."""

        if self._context_id != -1:
            return

        self._app = app
        self._context_id = context_id

    @property
    def app(self) -> App:
        return self._app

    @property
    def context_id(self) -> int:
        return self._context_id

    def as_tuple(self) -> tuple[int, int]:
        return self._app.id, self._context_id

    def __eq__(self, other):
        return isinstance(other, AppContext) and self.app.id == other.app.id and self.context_id == other.context_id

    def __hash__(self):
        return hash(self.as_tuple())

    @classmethod
    def get(cls, app: App, context_id: int) -> Self | None:
        """Get existing member."""
        return cls.__members__.get((app.id, context_id))

    @classmethod
    def add(cls, app_ctx: Self, force: bool = False):
        """Add new member regardless of ``ADD_NEW_MEMBERS`` flag."""

        if (existing := cls.get(app_ctx._app, app_ctx._context_id)) and not force:
            raise ValueError(f"{existing} already exists")

        cls.__members__[app_ctx.as_tuple()] = app_ctx


AppContext.CS2 = AppContext(App.CS2, 2)
AppContext.CS2_PROTECTED = AppContext(App.CS2, 16)

AppContext.DOTA2 = AppContext(App.DOTA2, 2)
AppContext.H1Z1 = AppContext(App.H1Z1, 2)
AppContext.RUST = AppContext(App.RUST, 2)
AppContext.TF2 = AppContext(App.TF2, 2)
AppContext.PUBG = AppContext(App.PUBG, 2)

AppContext.STEAM_GIFTS = AppContext(App.STEAM, 1)
AppContext.STEAM_COMMUNITY = AppContext(App.STEAM, 6)
AppContext.STEAM_REWARDS = AppContext(App.STEAM, 7)

AppContext.__members__.update(
    {
        ctx.as_tuple(): ctx
        for ctx in [
            AppContext.CS2,
            AppContext.CS2_PROTECTED,
            AppContext.DOTA2,
            AppContext.H1Z1,
            AppContext.RUST,
            AppContext.TF2,
            AppContext.PUBG,
            AppContext.STEAM_GIFTS,
            AppContext.STEAM_COMMUNITY,
            AppContext.STEAM_REWARDS,
        ]
    }
)
