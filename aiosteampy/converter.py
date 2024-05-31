"""Currency converter extension."""

import asyncio
from collections import UserDict
from datetime import datetime, timedelta

from yarl import URL
from aiohttp import ClientSession

try:
    from croniter import croniter

except ImportError:
    from warnings import warn

    warn(
        """
        The `aiosteampy.converter` module requires the `croniter` library to be installed
        to make the rates synchronization with backend service work.
        In order You need this functionality, You can use `aiosteampy[converter]` dependency install target.
        """,
        category=RuntimeWarning,
    )

    croniter = None


from .constants import Currency

__all__ = ("CurrencyConverter", "API_URL", "SERT_CRON")

API_URL = URL("https://sert.somespecial.one/")
SERT_CRON = "9,39 * * * ?"


class CurrencyConverter(UserDict[Currency, tuple[float, datetime]]):
    """
    Dict-like class to handle converting steam currencies.

    .. seealso:: https://github.com/somespecialone/sert
    """

    __slots__ = ("_cron", "api_url", "_sync_task")

    def __init__(self, *, api_url=API_URL, cron_exp=SERT_CRON):
        """
        :param api_url: url of `sert` backend service api
        :param cron_exp: cron expression string of `sert` backend service
        """

        super().__init__()

        self.api_url = api_url

        # normalize Deta cron expression
        self._cron = croniter(cron_exp.replace("?", "*"), ret_type=datetime) if croniter else None
        self._sync_task: asyncio.Task | None = None

    @property
    def currencies(self) -> list[Currency]:
        return list(self.keys())

    @property
    def expired(self) -> bool:
        """If at least one single currency rate was updated yesterday at the latest."""

        utcnow_date = datetime.utcnow().date()
        return any(updated.date() != utcnow_date for _, updated in self.values())

    async def load(self):
        """Load rates."""

        async with ClientSession() as sess:
            r = await sess.get(self.api_url / "rates")
            rj: dict[str, list[float, int]] = await r.json()

        for curr_key, v in rj.items():
            self[Currency.by_name(curr_key)] = (v[0], datetime.utcfromtimestamp(v[1]))

    def close(self):
        """
        Cancel inner `_sync_task` if it exists.
        Needed if You use a synchronization task (call `synchronize`previously).
        """

        self._sync_task and self._sync_task.cancel()

    def synchronize(self):
        """
        Synchronize rates with backend.
        Create background task.

        If you want handle task by yourself you can use `get_wait_time` method
        to get time in seconds for the next rate update on backend.
        """

        async def sync_coro():
            while self._cron:
                await asyncio.gather(
                    asyncio.sleep(self.get_wait_time()),
                    self.load(),
                )

        self._sync_task = asyncio.create_task(sync_coro())

    def get_wait_time(self) -> float:
        """Calculate time to nearest service rates update."""

        utcnow = datetime.utcnow()
        if self.expired:
            when = self._cron.get_next(start_time=utcnow)
        else:
            # go to the next day
            when = self._cron.get_next(start_time=utcnow.replace(hour=0, minute=0, second=0) + timedelta(days=1))

        wait = (when - utcnow) + timedelta(minutes=1)  # offset to ensure that service finish to update rates
        return wait.total_seconds()

    def convert(self, amount: int, currency: Currency, target=Currency.USD) -> int:
        """
        Convert amount from `currency` to `target` currency.

        :param amount: amount of currency that need to be converted
        :param currency: passed currency of `amount`
        :param target: target of returned value
        :return: converted amount
        :raises KeyError: if provided currency is not present in `Converter`
        """

        source_rate = self[currency][0] if currency is not Currency.USD else 1
        target_rate = self[target][0] if target is not Currency.USD else 1

        # direct conversion
        # return round(amount * (target_rate / source_rate))

        # with USD in middle step
        usd_amount = round(amount * (1 / source_rate))
        return round(usd_amount * target_rate)
