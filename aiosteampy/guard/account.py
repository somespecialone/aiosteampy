from dataclasses import asdict, dataclass
from typing import NotRequired, Self, TypedDict

from ..id import SteamID
from .secrets import IdentitySecret, SharedSecret, TwoFactorSecret


class MaFileSession(TypedDict):
    SteamID: int  # 64
    AccessToken: str
    RefreshToken: str
    SessionID: str


class MaFile(TypedDict):
    """`Steam Desktop Authenticator` file data."""

    shared_secret: str
    serial_number: str
    revocation_code: str
    uri: str
    server_time: int
    account_name: str
    token_gid: str
    identity_secret: str
    secret_1: str
    status: int
    device_id: str
    phone_number_hint: NotRequired[str]
    confirm_type: NotRequired[int]
    fully_enrolled: bool
    Session: MaFileSession


@dataclass(slots=True)
class SteamGuardAccount:
    """`Steam Guard` data representation."""

    account_name: str
    steam_id: SteamID
    device_id: str

    shared_secret: SharedSecret
    identity_secret: IdentitySecret
    secret_1: TwoFactorSecret

    revocation_code: str

    uri: str
    serial_number: int
    token_gid: str

    finalized: bool
    """Whether represents data of activated (enrolled) `Steam Guard` account."""

    def serialize(self) -> dict:
        """Export account data as `JSON-safe` dict."""

        data = asdict(self)
        data["shared_secret"] = self.shared_secret.serialize()
        data["identity_secret"] = self.identity_secret.serialize()
        data["secret_1"] = self.secret_1.serialize()
        return data

    @classmethod
    def deserialize(cls, serialized: dict) -> Self:
        """Import account data from `JSON-safe` dict."""

        account = cls(**serialized)
        account.steam_id = SteamID(account.steam_id)
        account.shared_secret = SharedSecret(serialized["shared_secret"])
        account.identity_secret = IdentitySecret(serialized["identity_secret"])
        account.secret_1 = TwoFactorSecret(serialized["secret_1"])
        return account

    @classmethod
    def from_mafile(cls, mafile: MaFile) -> Self:
        return cls(
            account_name=mafile["account_name"],
            steam_id=SteamID(mafile["Session"]["SteamID"]),
            device_id=mafile["device_id"],
            shared_secret=SharedSecret(mafile["shared_secret"]),
            identity_secret=IdentitySecret(mafile["identity_secret"]),
            secret_1=TwoFactorSecret(mafile["secret_1"]),
            revocation_code=mafile["revocation_code"],
            uri=mafile["uri"],
            serial_number=int(mafile["serial_number"]),
            token_gid=mafile["token_gid"],
            finalized=mafile.get("fully_enrolled", True),  # for Nebula SDA
        )
