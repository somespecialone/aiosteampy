"""Client for interacting with `ISteamNotificationService`."""

from collections.abc import Awaitable

from ..protobufs.notification import *
from ._base import SteamWebApiServiceBase


class NotificationServiceClient(SteamWebApiServiceBase):
    """Notifications service client."""

    __slots__ = ()

    SERVICE_NAME = "ISteamNotificationService"

    async def get_steam_notifications(
        self,
        include_hidden: bool = False,
        language: int = 0,
        include_confirmation_count: bool = True,
        include_pinned_counts: bool = False,
        include_read: bool = True,
        count_only: bool = False,
    ) -> CSteamNotificationGetSteamNotificationsResponse:
        msg = CSteamNotificationGetSteamNotificationsRequest(
            include_hidden=include_hidden,
            language=language,
            include_confirmation_count=include_confirmation_count,
            include_pinned_counts=include_pinned_counts,
            include_read=include_read,
            count_only=count_only,
        )
        r = await self._proto("GetSteamNotifications", msg, http_method="GET", auth=True)
        return CSteamNotificationGetSteamNotificationsResponse.parse(r)

    def mark_notifications_viewed(self) -> Awaitable[None]:
        msg = CSteamNotificationMarkNotificationsViewedNotification()
        return self._proto("MarkNotificationsViewed", msg, auth=True, response_mode="meta")

    def mark_notifications_read(
        self,
        notification_ids: list[int] = (),
        timestamp: int = 0,
        notification_type: ESteamNotificationType = ESteamNotificationType.k_ESteamNotificationType_Invalid,
        mark_all_read: bool = False,
    ) -> Awaitable[None]:
        msg = CSteamNotificationMarkNotificationsReadNotification(
            timestamp=timestamp,
            notification_type=notification_type,
            notification_ids=notification_ids,
            mark_all_read=mark_all_read,
        )
        return self._proto("MarkNotificationsRead", msg, auth=True, response_mode="meta")
