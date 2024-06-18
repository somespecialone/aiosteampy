"""User agents service extension."""

from collections import UserList
from random import choice

from yarl import URL
from aiohttp import ClientSession

API_URL = URL("https://randua.somespecial.one")


class UserAgentsService(UserList[str]):
    """
    List-like class of user agents responsible for loading and getting random user agents.

    .. seealso:: https://github.com/somespecialone/random-user-agent
    """

    __slots__ = ("_api_url",)

    def __init__(self, *, api_url=API_URL):
        """
        :param api_url: url of `random user agent` backend service api
        """

        super().__init__()

        self._api_url = api_url

    @property
    def agents(self) -> list[str]:
        return self.data

    async def load(self):
        async with ClientSession(raise_for_status=True) as sess:
            r = await sess.get(self._api_url / "all")
            agents: list[str] = (await r.text()).splitlines()

        self.data = agents

    def get_random(self) -> str:
        return choice(self.agents)
