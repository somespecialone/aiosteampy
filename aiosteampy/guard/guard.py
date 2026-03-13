from collections.abc import Awaitable

from yarl import URL

from ..session import SteamSession, parse_qr_challenge_url
from .confirmation import SteamConfirmations
from .signer import TwoFactorSigner


class SteamGuard:
    __slots__ = ("_session", "_conf")

    def __init__(
        self,
        session: SteamSession,
        shared_secret: str,
        identity_secret: str,
        device_id: str | None = None,
        time_offset: int = 0,
    ):
        """
        `Steam Guard` implementation.

        :param session: authenticated session.
        :param shared_secret: shared secret of account.
        :param identity_secret: identity secret of account.
        :param device_id: generated device id.
        :param time_offset: known offset in seconds from server time.
        """

        if not session.is_mobile:
            raise ValueError("Session must be mobile")
        if session.access_token is None:
            raise ValueError("Session must be authenticated")

        self._session = session

        signer = TwoFactorSigner(session.steam_id, shared_secret, identity_secret, session.webapi, time_offset)
        self._conf = SteamConfirmations(session, signer, device_id)

    @property
    def session(self) -> SteamSession:
        return self._session

    @property
    def confirmations(self) -> SteamConfirmations:
        return self._conf

    @property
    def signer(self):
        return self._conf.signer

    # does not requires auth, but anyway
    def confirm_auth_request(
        self,
        obj: str | URL | tuple[int, int],
        *,
        confirm: bool = True,
        persistence: bool = True,
    ) -> Awaitable[None]:
        """
        Perform mobile confirmation of the other `login session` login request.

        Equivalent of scanning auth QR with Steam App on a mobile device and tapping "Approve" or "Decline" button
        as the next step.

        :param obj: QR challenge url of `session` or tuple of version and client id.
        :param confirm: confirm the `session` or not.
        :param persistence: should `session` be persistent.
        """

        if isinstance(obj, (str, URL)):
            version, client_id = parse_qr_challenge_url(obj)
        else:
            version, client_id = obj

        signature = self._conf.signer.sign_auth_request(version, client_id)

        return self._session.service.update_auth_session_with_mobile_confirmation(
            version,
            client_id,
            self._session.steam_id,
            signature,
            confirm=confirm,
            persistence=persistence,
        )

    async def approve_session(
        self,
        session: SteamSession,
        *,
        persistence: bool = True,
        device_friendly_name: str | None = None,
    ):
        """
        Approve other ``SteamSession``.
        Passed ``session`` will be finalized, authenticated and ready to use after approval.

        Equivalent of scanning auth QR with `Steam App` on a mobile device
        and tapping "Approve" button as the next step.

        :param session: ``SteamSession`` to approve.
            Must be **blank**, from the same account and with **non-mobile app** platform type.
        :param persistence: should `session` be persistent.
        :param device_friendly_name: name of the device used for authentication.
            Should be unique, identifiable, and human readable. Used when managing account sessions.
        :raises LoginError: for ordinary reasons.
        :raises ValueError: when passed `session` is already initialized or has mobile app platform type.
        """

        if session is self._session:
            raise ValueError("Cannot approve current session")
        if session.is_mobile:
            raise ValueError("Only session with non-mobile app platform type can be approved")
        if session.refresh_token is not None:
            raise ValueError("Passed session is not blank")

        version, client_id, _, _ = await session.with_qr(device_friendly_name)
        await self.confirm_auth_request((version, client_id), persistence=persistence)
        await session.finalize()

    async def add_phone_number(self, phone_number: str):
        """Add phone number to account."""
        raise NotImplementedError

    async def enable_two_factor(self, auth_code: str):
        """Enable two-factor auth for account."""
        raise NotImplementedError

    # https://github.com/DoctorMcKay/node-steamcommunity/blob/d3e90f6fd3bea65b1ebc1bdaec754f99dcc8ddb3/components/twofactor.js#L117
    async def remove_two_factor(self, revocation_code: str):
        """Remove two-factor auth from account."""

        raise NotImplementedError

        # data = {
        #     "steamid": self._session.steam_id.id64,
        #     "revocation_code": revocation_code,
        #     "steamguard_scheme": 1,
        # }
        # r: dict[str, dict] = await self._session.webapi.request(
        #     "POST",
        #     "ITwoFactorService/RemoveAuthenticator",
        #     multipart=data,
        #     auth=True,
        # )
        #
        # if not r["response"].get("success"):
        #     raise ...

    # TODO from/to maFile
