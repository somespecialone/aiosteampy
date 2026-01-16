from typing import Literal, Any, Mapping, Self

JSON_SAFE_COOKIE_DICT = dict[str, str | int | bool | dict[str, Any] | None]

HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]  # will be used first two, however
Headers = Mapping[str, str]
Params = Mapping[str, Any]
Payload = Mapping[str, Any]
ResponseMode = Literal["bytes", "json", "text", "meta"]  # Enum is not worth it

# Steam Web API
# Option interface+dedicated methods with overload does not work with default str type for non-predefined literals
# so let it be just unions of all predefined interfaces and methods. User of method responsible to not mess them
WebAPIInterface = Literal["IEconService", "IAuthenticationService", "ITwoFactorService"]
WebAPIMethod = Literal[
    # IEconService
    "GetTradeHistory",
    "GetTradeHoldDurations",
    "GetTradeOffer",
    "GetTradeOffers",
    "GetTradeOffersSummary",
    "GetTradeStatus",
    # IAuthenticationService
    "BeginAuthSessionViaCredentials",
    "BeginAuthSessionViaQR",
    "GetPasswordRSAPublicKey",
    "UpdateAuthSessionWithSteamGuardCode",
    "PollAuthSessionStatus",
    "GenerateAccessTokenForApp",
    "GetAuthSessionInfo",
    "UpdateAuthSessionWithMobileConfirmation",
    # ITwoFactorService
    "AddAuthenticator",
    "FinalizeAddAuthenticator",
    "RemoveAuthenticator",
]
WebAPIVersion = Literal["v1"]
