"""Component responsible for `Steam` user notifications functionality."""

from collections.abc import Awaitable

from ...session import SteamSession
from ...webapi.services.notification import (
    CSteamNotificationGetSteamNotificationsResponse,
    NotificationServiceClient,
)


class NotificationsComponent:
    """Component responsible for `Steam` user notifications functionality."""

    __slots__ = ("_session", "_service")

    def __init__(self, session: SteamSession):
        self._session = session
        self._service = NotificationServiceClient(session.webapi)

    @property
    def service(self) -> NotificationServiceClient:
        """Notifications service client."""
        return self._service

    # need to add custom models here
    def get(self) -> Awaitable[CSteamNotificationGetSteamNotificationsResponse]:
        """Get all standing notifications."""
        return self._service.get_steam_notifications()

    async def mark_all_read(self):
        """Mark all standing notifications as read."""

        await self._service.mark_notifications_viewed()  # firstly mark as viewed as browser does
        await self._service.mark_notifications_read(mark_all_read=True)  # then mark all read
