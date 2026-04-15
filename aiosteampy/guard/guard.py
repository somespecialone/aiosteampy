import time
from collections.abc import Awaitable
from typing import Self

from yarl import URL

from ..constants import EResult
from ..exceptions import EmailConfirmationRequired, EResultError, Unauthenticated
from ..session import SteamSession, generate_session_id, parse_qr_challenge_url
from ..session.session import QRChallengeUrl
from ..transport import BaseSteamTransport
from ..webapi import SteamWebAPIClient
from ..webapi.services.phone import PhoneServiceClient
from ..webapi.services.twofactor import (
    CTwoFactorAddAuthenticatorResponse,
    CTwoFactorStatusResponse,
    TwoFactorServiceClient,
)
from .account import MaFile, SteamGuardAccount
from .confirmations import SteamConfirmations
from .exceptions import (
    AuthenticatorAlreadyPresent,
    AuthenticatorError,
    SmsConfirmationRequired,
    TooManyAttempts,
    TwoFactorCodeMismatch,
)
from .secrets import IdentitySecret, SharedSecret, TwoFactorSecret
from .signer import TwoFactorSigner
from .utils import generate_device_id


class SteamGuard:
    __slots__ = (
        "_session",
        "_device_id",
        "_conf",
        "_phone",
        "_2fa",
        "_2fa_resp",
        "_time_offset",
        "_2fa_finalized",
        "_account_has_been_exported",
    )

    def __init__(
        self,
        session: SteamSession,
        *,
        shared_secret: str | bytes | None = None,
        identity_secret: str | bytes | None = None,
        device_id: str | None = None,
        time_offset: int | None = None,
    ):
        """
        `Steam Guard` implementation.

        Both `secrets` must be provided.

        :param session: authenticated session.
        :param shared_secret: shared secret of an account in bytes or base64 encoded string.
        :param identity_secret: identity secret of an account in bytes or base64 encoded string.
        :param device_id: generated device id.
        :param time_offset: known offset in seconds from server time.
        """

        # need to be initialized first as referenced in __del__
        self._account_has_been_exported: bool = False
        self._2fa_resp: CTwoFactorAddAuthenticatorResponse | None = None
        self._2fa_finalized: bool = False

        if not session.is_mobile:
            raise ValueError("Session must be mobile")
        if session.access_token is None:
            raise Unauthenticated
        if (not shared_secret and identity_secret) or (shared_secret and not identity_secret):
            raise ValueError("Both shared and identity secrets must be provided")

        self._session = session
        self._device_id = device_id or generate_device_id()

        if shared_secret:
            if not session.cookies_are_valid:  # preventing user from accessing confirmations with missing cookies
                raise Unauthenticated

            signer = TwoFactorSigner(
                session.steam_id,
                shared_secret=shared_secret,
                identity_secret=identity_secret,
                webapi=session.webapi,
                time_offset=time_offset,
            )
            self._conf = SteamConfirmations(session, signer, self._device_id)
        else:
            self._conf = None

        self._phone = PhoneServiceClient(session.webapi)
        self._2fa = TwoFactorServiceClient(session.webapi)

        self._time_offset = time_offset

    @property
    def session(self) -> SteamSession:
        """Authenticated `Steam` session."""
        return self._session

    @property
    def device_id(self) -> str:
        """Mobile device id."""
        return self._device_id

    @property
    def confirmations(self) -> SteamConfirmations | None:
        """`Steam` mobile confirmations manager."""
        return self._conf

    @property
    def signer(self) -> TwoFactorSigner | None:
        """Crypto signer."""
        return self._conf.signer if self._conf is not None else None

    @property
    def two_factor_service(self) -> TwoFactorServiceClient:
        """TwoFactor service client."""
        return self._2fa

    @property
    def phone_service(self) -> PhoneServiceClient:
        """Phone service client."""
        return self._phone

    @property
    def webapi(self) -> SteamWebAPIClient:
        """`Steam Web API` client."""
        return self._session.webapi

    @property
    def transport(self) -> BaseSteamTransport:
        """HTTP transport instance."""
        return self._session.transport

    def _confirm_auth_request(self, qr: QRChallengeUrl, confirm: bool, *, persistence: bool = True) -> Awaitable[None]:
        if self._conf is None:
            raise ValueError("Current account must posses enabled two-factor with secrets to confirm auth request")

        if isinstance(qr, (str, URL)):
            version, client_id = parse_qr_challenge_url(qr)
        else:
            version, client_id = qr

        signature = self._conf.signer.sign_auth_request(version, client_id)

        return self._session.service.update_auth_session_with_mobile_confirmation(
            version,
            client_id,
            self._session.steam_id,
            signature,
            confirm=confirm,
            persistence=persistence,
        )

    def approve_auth_request(self, qr: QRChallengeUrl, *, persistence: bool = True) -> Awaitable[None]:
        """
        Approvee other `login session` auth request.

        Equivalent of scanning auth QR with Steam App on a mobile device and tapping "Approve".

        :param qr: QR challenge url of `session` or tuple of version and client id.
        :param persistence: should `session` be persistent.
        :raises TransportError: ordinary reasons.
        :raises EResultError: ordinary reasons.
        """

        return self._confirm_auth_request(qr, True, persistence=persistence)

    def deny_auth_request(self, qr: QRChallengeUrl) -> Awaitable[None]:
        """
        Deny other `login session` auth request.

        Equivalent of scanning auth QR with Steam App on a mobile device and tapping "Decline".

        :param qr: QR challenge url of `session` or tuple of version and client id.
        :raises TransportError: ordinary reasons.
        :raises EResultError: ordinary reasons.
        """

        return self._confirm_auth_request(qr, False)

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
            Should be unique, identifiable, and human-readable. Used when managing account sessions.
        :raises TransportError: ordinary reasons.
        :raises EResultError: ordinary reasons.
        :raises LoginError: ordinary reasons.
        :raises TooManyAttempts: when `Steam` rejects credentials due to too many attempts.
        """

        if session is self._session:
            raise ValueError("Cannot approve current session")
        if session.is_mobile:
            raise ValueError("Only session with non-mobile app platform type can be approved")
        if session.refresh_token is not None:
            raise ValueError("Passed session is not blank")
        if self._conf is None:
            raise ValueError("Current account must posses enabled two-factor with secrets to confirm auth request")

        version, client_id, _, _ = await session.with_qr(device_friendly_name)
        await self.approve_auth_request((version, client_id), persistence=persistence)
        await session.finalize()

    async def enable(self):
        """
        Initialize enabling process of `Steam Guard`
        (two-factor authentication and confirmations) for account.

        This method will *definitely raise an exception* signaling
        what confirmation is needed to continue (either `SMS` or `email`).

        :raises TransportError: ordinary reasons.
        :raises AuthenticatorError: ordinary reasons.
        :raises AuthenticatorAlreadyPresent: when `two-factor` auth is already enabled.
        :raises TooManyAttempts: when `Steam` rejects enabling due to too many attempts.
        :raises SmsConfirmationRequired: `SMS` confirmation is required.
        :raises EmailConfirmationRequired: `Email` confirmation is required.
        """

        if self._2fa_resp is not None:
            raise ValueError("Two-factor is already enabled or in progress")

        try:
            r = await self._2fa.add_authenticator(self._session.steam_id, self._device_id)
        except EResultError as e:  # here we can get EResultError
            match e.result:
                case EResult.DUPLICATE_REQUEST:  # r.status == 29
                    raise AuthenticatorAlreadyPresent
                case EResult.NO_VERIFIED_PHONE:  # r.status == 2
                    raise AuthenticatorError(
                        "No verified phone number. This error must never happen, please report to a maintainers"
                    )
                case EResult.RATE_LIMIT_EXCEEDED:  # r.status == 84??
                    raise TooManyAttempts
                case unknown:
                    raise AuthenticatorError(f"Unknown EResult: {unknown.name}") from e

        if r.status != 1:  # must be equal to header, but let's be vigilant
            raise AuthenticatorError(f"Unknown response status: {r.status}")

        self._2fa_resp = r
        if self._time_offset is None:  # respect user defined offset
            self._time_offset = r.server_time - int(time.time())

        match r.confirm_type:
            case 1:
                raise SmsConfirmationRequired(r.phone_number_hint)
            case 3:
                raise EmailConfirmationRequired
            case unknown:
                raise AuthenticatorError(f"Unknown confirmation type: {unknown}")

    async def finalize(self, activation_code: str):
        """
        Finalize enabling process of `Steam Guard` (two-factor) for account.
        ``RuntimeError`` is raised if something goes wrong during finalization.
        For safety measures data will be attached to exception and warning will be raised.

        Activated `Guard` account can be retrieved after successful finalization
        with ``export_account`` or ``export_mafile`` method from current instance.

        .. note::
            It is worth mentioning that **DATA BETTER BE SAVED ASAP**
            to prevent possible loss after successful finalization.

        :param activation_code: code from `Steam` received either by `SMS` or `email`.
        :return: activated account data.
        :raises TransportError: ordinary reasons.
        :raises AuthenticatorError: ordinary reasons.
        :raises TwoFactorCodeMismatch: when ``activation_code`` is incorrect.
        :raises RuntimeError: when something goes wrong during finalization.
        """

        if self._2fa_finalized:
            raise ValueError("Two-factor is already enabled")

        account = self._get_account()  # 2fa resp will be checked there

        signer = TwoFactorSigner(
            self._session.steam_id,
            shared_secret=account.shared_secret,
            identity_secret=account.identity_secret,
            webapi=self.webapi,
            time_offset=self._time_offset,
        )

        try:
            r = await self._2fa.finalize_add_authenticator(
                steamid=self._session.steam_id,
                authenticator_code=signer.generate_auth_code(),
                # we generate codes respecting server time, do we need to pass here our time?
                authenticator_time=int(time.time()),
                activation_code=activation_code,
                validate_sms_code=self._2fa_resp.confirm_type == 1,  # if SMS were required
            )

        except Exception as e:
            import warnings

            account_data = account.serialize()

            msg = (
                "Unknown error have happened during two-factor activation. "
                "This can be really bad if finalization is successful. "
                "In that case here is the guard data: "
            )

            warnings.warn(msg + str(account_data), RuntimeWarning)
            raise RuntimeError(msg, account_data) from e

        if r.success:  # seems most reliable way to check activation status
            self._2fa_finalized = True
            self._conf = SteamConfirmations(self._session, signer, self._device_id)
            return

        # EResult.OK in header even if activation failed, we cannot believe Steam even in that.
        # Moreover, r.status will be 2 (EResult.FAIL) in case of successful activation!
        match EResult(r.status):
            case EResult.TWO_FACTOR_ACTIVATION_CODE_MISMATCH:  # passed wrong activation code
                raise TwoFactorCodeMismatch
            case EResult.TWO_FACTOR_CODE_MISMATCH:  # generated auth code is incorrect
                raise AuthenticatorError(
                    "Generated auth code by signer is incorrect, "
                    "which normally should never happen. "
                    "Please report to maintainers"
                )
            case unknown:
                raise AuthenticatorError(f"Unknown EResult: {unknown.name}")

    async def disable(self, revocation_code: str, switch_to_email: bool = True):
        """
        Disable `Steam Guard` (two-factor) for account.

        :param revocation_code: code from saved `Guard` account saved.
        :param switch_to_email: whether `Guard` should be switched to receiving `email` codes.
            if ``False``, `Guard` will be completely removed.
        :raises TransportError: ordinary reasons.
        :raises AuthenticatorError: ordinary reasons.
        :raises TwoFactorCodeMismatch: when ``activation_code`` is incorrect.
        """

        r, e = await self._2fa.remove_authenticator(revocation_code, 1 if switch_to_email else 2)
        if e is not None:
            if e.result is EResult.TWO_FACTOR_CODE_MISMATCH:
                raise TwoFactorCodeMismatch(r.revocation_attempts_remaining)
            else:
                raise AuthenticatorError(f"Unknown EResult: {e.result.name}") from e

        if not r.success:
            raise AuthenticatorError(f"Unknown error", r)

        self._2fa_resp = None
        self._2fa_finalized = False
        self._conf = None
        self._account_has_been_exported = False

    def get_status(self, include_last_usage: bool = False) -> Awaitable[CTwoFactorStatusResponse]:
        """Get current `Steam Guard` status."""
        return self._2fa.query_status(self._session.steam_id, include_last_usage)

    def _get_account(self) -> SteamGuardAccount:
        """Create account without marking it as exported."""

        if self._2fa_resp is None:
            raise ValueError("There is no account data as two-factor enabling is not in the progress")

        return SteamGuardAccount(
            account_name=self._2fa_resp.account_name,
            steam_id=self._session.steam_id,
            device_id=self._device_id,
            shared_secret=SharedSecret(self._2fa_resp.shared_secret),
            identity_secret=IdentitySecret(self._2fa_resp.identity_secret),
            secret_1=TwoFactorSecret(self._2fa_resp.secret_1),
            revocation_code=self._2fa_resp.revocation_code,
            uri=self._2fa_resp.uri,
            serial_number=self._2fa_resp.serial_number,
            token_gid=self._2fa_resp.token_gid,
            finalized=self._2fa_finalized,
        )

    def export_account(self) -> SteamGuardAccount:
        """Export enabled `Steam Guard` (two-factor) account data."""

        account = self._get_account()
        self._account_has_been_exported = True
        return account

    def export_mafile(self) -> MaFile:
        """Export `Steam Guard` account as `Steam Desktop Authenticator` file (maFile)."""

        account = self.export_account().serialize()
        return MaFile(
            shared_secret=account["shared_secret"],
            serial_number=str(account["serial_number"]),
            revocation_code=account["revocation_code"],
            uri=account["uri"],
            server_time=self._2fa_resp.server_time,
            account_name=account["account_name"],
            token_gid=account["token_gid"],
            identity_secret=account["identity_secret"],
            secret_1=account["secret_1"],
            status=self._2fa_resp.status,
            device_id=account["device_id"],
            phone_number_hint=self._2fa_resp.phone_number_hint,
            confirm_type=self._2fa_resp.confirm_type,
            fully_enrolled=self._2fa_finalized,
            Session={
                "SteamID": account["steam_id"],
                "AccessToken": self._session.access_token.raw,
                "RefreshToken": self._session.refresh_token.raw,
                "SessionID": self._session.session_id or generate_session_id(),
            },
        )

    # async def add_phone_number(self, country_code: str, phone_number: str):
    #     """Add phone number to account."""
    #     raise NotImplementedError

    def __del__(self):
        if self._2fa_resp is not None and self._2fa_finalized and not self._account_has_been_exported:
            # warn user that account data was not exported and the instance is about to be destroyed
            import warnings

            data = self.export_account().serialize()
            warnings.warn(
                "Steam Guard account data was not exported! Store it somewhere safe: " + str(data),
                UserWarning,
            )

    @classmethod
    def from_account(cls, account: SteamGuardAccount, session: SteamSession) -> Self:
        """Create ``SteamGuard`` from a finalized and previously exported ``account``."""

        if not account.finalized:
            raise ValueError("Account is not finalized")
        if account.steam_id != session.steam_id:
            raise ValueError("Steam Guard steam ID does not match session steam ID")

        guard = cls(
            session,
            shared_secret=account.shared_secret,
            identity_secret=account.identity_secret,
            device_id=account.device_id,
        )
        guard._2fa_finalized = True

        return guard

    @classmethod
    async def from_mafile(
        cls,
        mafile: MaFile,
        transport: BaseSteamTransport | None = None,
        proxy: str | None = None,
    ) -> Self:
        """Create ``SteamGuard`` from ``mafile``. Will obtain auth cookies automatically."""

        if not mafile.get("fully_enrolled", True):
            raise ValueError("Account from maFile must be fully enrolled")

        session = SteamSession(
            mafile["Session"]["AccessToken"],
            mafile["Session"]["RefreshToken"],
            transport=transport,
            proxy=proxy,
            _ignore_expired=True,
        )

        session._session_id = mafile["Session"]["SessionID"]

        if session.access_token.expired:
            await session.refresh_access_token()
            await session.obtain_cookies()
        elif not session.cookies_are_valid:
            await session.obtain_cookies()

        guard = cls(
            session,
            shared_secret=mafile["shared_secret"],
            identity_secret=mafile["identity_secret"],
            device_id=mafile["device_id"],
        )
        guard._2fa_finalized = True

        return guard
