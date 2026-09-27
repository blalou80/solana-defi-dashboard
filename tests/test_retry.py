"""Retry semantics tests (Phase 0 fix #4).

Regression guard for the bug where the *sync* ``retry`` decorator was
applied to ``async def`` methods: the wrapper returned the coroutine
un-awaited, so retries never fired and the first failure escaped.
"""

import pytest

from src.utils import async_retry

pytestmark = pytest.mark.asyncio


# --- async_retry itself -------------------------------------------------

calls = {"n": 0}


@async_retry(max_attempts=3, delay=0.01, backoff=1.0)
async def flaky():
    calls["n"] += 1
    if calls["n"] < 3:
        raise ConnectionError("boom")
    return "ok"


async def test_async_retry_retries_until_success():
    calls["n"] = 0
    assert await flaky() == "ok"
    assert calls["n"] == 3


@async_retry(max_attempts=2, delay=0.01, backoff=1.0)
async def always_fails():
    raise ConnectionError("nope")


async def test_async_retry_raises_after_exhausting():
    with pytest.raises(ConnectionError):
        await always_fails()


# --- the decorated service methods must actually retry ------------------

class _FakeResp:
    def __init__(self, ok_after: int):
        self.ok_after = ok_after
        self.n = 0

    async def __aenter__(self):
        self.n += 1
        if self.n < self.ok_after:
            raise ConnectionError("transient")
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        return None

    async def json(self):
        return {"value": 42}


class _FakeSession:
    closed = False

    def __init__(self, resp):
        self.resp = resp

    def request(self, *a, **k):
        return self.resp


async def test_dex_client_request_retries_transient_failures():
    from src.services.dex_api_client import DexApiClient

    client = DexApiClient("http://example.invalid", rate_limit_per_sec=1000)
    resp = _FakeResp(ok_after=2)  # fail once, then succeed
    client._session = _FakeSession(resp)

    result = await client._request("GET", "/x")
    assert result == {"value": 42}
    assert resp.n == 2  # proves the retry loop executed


async def test_rpc_client_account_info_is_awaitable_and_retries():
    """A sync @retry on an async def returned a coroutine from a non-async
    wrapper; calling code awaiting it masked the missing retry. Verify the
    method now retries by patching the underlying solana client."""
    from src.services.solana_rpc_client import SolanaRpcClient

    client = SolanaRpcClient("http://127.0.0.1:1")  # never connected directly

    state = {"n": 0}

    class _Resp:
        value = None

    async def flaky_get_account_info(*a, **k):
        state["n"] += 1
        if state["n"] < 2:
            raise ConnectionError("transient")
        return _Resp()

    client.client.get_account_info = flaky_get_account_info
    result = await client.get_account_info(
        "So11111111111111111111111111111111111111112"
    )
    assert result is None  # response.value was None
    assert state["n"] == 2  # retried once
    await client.close()
