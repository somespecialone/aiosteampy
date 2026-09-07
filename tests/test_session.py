import json
from base64 import urlsafe_b64encode
from unittest.mock import AsyncMock, call

import pytest

from aiosteampy.constants import EResult
from aiosteampy.exceptions import EResultError
from aiosteampy.session import SteamSession
from aiosteampy.webapi.protobufs.auth import CAuthenticationPollAuthSessionStatusResponse
from aiosteampy.webapi.services.auth import AuthenticationServiceClient


def make_test_token(audiences):
    """Create an unsigned, synthetic token for local parsing; never sent to Steam."""
    header = {"alg": "none", "typ": "JWT"}
    claims = {"sub": "0", "aud": audiences, "iat": 0, "exp": 4102444800}
    parts = [urlsafe_b64encode(json.dumps(part).encode()).rstrip(b"=").decode() for part in (header, claims)]
    return ".".join([*parts, ""])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("new_client_ids", "expected_client_ids"),
    [
        ([0, 0], [100, 100, 100]),
        ([200, 0], [100, 200, 200]),
        ([200, 300], [100, 200, 300]),
    ],
    ids=["unchanged", "rotated-then-omitted", "rotated-twice"],
)
async def test_finalize_polls_with_current_client_id(monkeypatch, new_client_ids, expected_client_ids):
    access_token = make_test_token(["web"])
    refresh_token = make_test_token(["web", "derive"])
    responses = [CAuthenticationPollAuthSessionStatusResponse(new_client_id=value) for value in new_client_ids]
    responses.append(
        CAuthenticationPollAuthSessionStatusResponse(
            account_name="test_user", access_token=access_token, refresh_token=refresh_token
        )
    )
    poll = AsyncMock(side_effect=responses)
    monkeypatch.setattr(AuthenticationServiceClient, "poll_auth_session_status", poll)

    session = SteamSession()
    try:
        session._set_state(request_id=b"test-request", client_id=100, poll_interval=0)
        access, refresh = await session.finalize(timeout=1)

        assert poll.await_args_list == [call(value, b"test-request") for value in expected_client_ids]
        assert access.raw == access_token
        assert refresh.raw == refresh_token
        assert session.account_name == "test_user"
        assert session._client_id == 0
        assert session._request_id == b""
    finally:
        await session.transport.close()


@pytest.mark.asyncio
async def test_finalize_propagates_poll_error_after_client_id_rotation(monkeypatch):
    error = EResultError(EResult.EXPIRED, "Test session expired")
    poll = AsyncMock(side_effect=[CAuthenticationPollAuthSessionStatusResponse(new_client_id=200), error])
    monkeypatch.setattr(AuthenticationServiceClient, "poll_auth_session_status", poll)

    session = SteamSession()
    try:
        session._set_state(request_id=b"test-request", client_id=100, poll_interval=0)
        with pytest.raises(EResultError) as raised:
            await session.finalize(timeout=1)

        assert raised.value is error
        assert poll.await_args_list == [call(100, b"test-request"), call(200, b"test-request")]
        assert session._client_id == 0
        assert session._request_id == b""
    finally:
        await session.transport.close()
