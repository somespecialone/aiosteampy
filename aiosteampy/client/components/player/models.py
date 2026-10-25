from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, kw_only=True)
class PlayerGame:
    appid: int
    name: str
    playtime_forever: int
    playtime_2weeks: int | None = None
    img_icon_url: str | None = None
    img_logo_url: str | None = None
    rtime_last_played: datetime | None = None


@dataclass(slots=True, kw_only=True)
class OwnedGamesResponse:
    game_count: int
    games: list[PlayerGame]


@dataclass(slots=True, kw_only=True)
class RecentlyPlayedGamesResponse:
    total_count: int
    games: list[PlayerGame]
