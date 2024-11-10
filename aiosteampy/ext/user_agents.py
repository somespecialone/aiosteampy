"""User agents service extension."""

from collections import UserList
from random import choice

from yarl import URL
from aiohttp import ClientSession

__all__ = ("UserAgentsService", "SOURCE_URL")

SOURCE_URL = URL("https://raw.githubusercontent.com/somespecialone/random-user-agent/refs/heads/master/ua.txt")


class UserAgentsService(UserList[str]):
    """
    List-like class of user agents responsible for loading and getting random user agents.

    .. seealso:: https://github.com/somespecialone/random-user-agent
    """

    @property
    def agents(self) -> list[str]:
        return self.data

    async def load(self, source_url=SOURCE_URL):
        """Load random user agents from `source url`"""

        async with ClientSession(raise_for_status=True) as sess:
            r = await sess.get(source_url)
            agents: list[str] = (await r.text()).splitlines()

        self.data = agents

    def get_random(self) -> str:
        return choice(self.agents)
