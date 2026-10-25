"""Client for interacting with `IPlayerService`."""

import json

from ._base import JsonResponse, SteamWebApiServiceBase


class PlayerServiceClient(SteamWebApiServiceBase):
    """Player service client."""

    __slots__ = ()

    SERVICE_NAME = "IPlayerService"

    async def get_owned_games(
        self, steamid: int, include_appinfo: bool, include_played_free_games: bool, appids_filter: list[int]
    ) -> JsonResponse:
        params: dict[str, str | int] = {
            "input_json": json.dumps(
                {
                    "steamid": steamid,
                    "include_appinfo": int(include_appinfo),
                    "include_played_free_games": int(include_played_free_games),
                    "appids_filter": appids_filter,
                }
            )
        }
        return await self._urlencoded("GetOwnedGames", params=params, auth=True)

    async def get_recently_played_games(self, steamid: int, count: int) -> JsonResponse:
        params: dict[str, str | int] = {"steamid": steamid, "count": count}
        return await self._urlencoded("GetRecentlyPlayedGames", params=params, auth=True)
