"""Component responsible for `Steam` IPlayerService functionality."""

from datetime import UTC, datetime

from ....session import SteamSession
from ....webapi.services.player import PlayerServiceClient
from .models import OwnedGamesResponse, PlayerGame, RecentlyPlayedGamesResponse


class PlayerComponent:
    """Component responsible for `Steam` IPlayerService functionality."""

    __slots__ = ("_session", "_service")

    def __init__(self, session: SteamSession):
        self._session = session
        self._service = PlayerServiceClient(session.webapi)

    @property
    def service(self) -> PlayerServiceClient:
        """Player service client."""
        return self._service

    @classmethod
    def _build_public_image_url(cls, appid: str, image_hash: str | None) -> str | None:
        if image_hash is None:
            return None
        return f"https://media.steampowered.com/steamcommunity/public/images/apps/{appid}/{image_hash}.jpg"

    @classmethod
    def _parse_player_game(cls, game_data: dict) -> PlayerGame:
        appid = int(game_data["appid"])

        return PlayerGame(
            appid=appid,
            name=str(game_data["name"]) if "name" in game_data else None,
            img_icon_url=cls._build_public_image_url(appid, game_data.get("img_icon_url")),
            img_logo_url=cls._build_public_image_url(appid, game_data.get("img_logo_url")),
            playtime_2weeks=int(game_data["playtime_2weeks"]) if "playtime_2weeks" in game_data else None,
            playtime_forever=game_data["playtime_forever"],
            rtime_last_played=datetime.fromtimestamp(game_data["rtime_last_played"], UTC)
            if "rtime_last_played" in game_data and game_data["rtime_last_played"] != 0
            else None,
        )

    async def get_owned_games(
        self, *, steam_id=None, include_appinfo=False, include_played_free_games=True, appids_filter=[]
    ) -> OwnedGamesResponse:
        """Get all owned games."""
        data = await self._service.get_owned_games(
            steamid=self._session.steam_id if steam_id is None else steam_id,
            include_appinfo=include_appinfo,
            include_played_free_games=include_played_free_games,
            appids_filter=appids_filter,
        )

        return OwnedGamesResponse(
            game_count=int(data["response"]["game_count"]),
            games=[self._parse_player_game(game_data) for game_data in data["response"]["games"]],
        )

    async def get_recently_played_games(self, *, steam_id=None, count=0) -> RecentlyPlayedGamesResponse:
        """Get recently-played games."""

        data = await self._service.get_recently_played_games(
            steamid=self._session.steam_id if steam_id is None else steam_id, count=count
        )

        return RecentlyPlayedGamesResponse(
            total_count=data["response"]["total_count"],
            games=[self._parse_player_game(game_data) for game_data in data["response"]["games"]],
        )
