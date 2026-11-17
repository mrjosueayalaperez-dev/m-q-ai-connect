import pytest
from fastapi.testclient import TestClient

from app.db import connect

# Batch 008 — deny-by-default API. The API no longer treats a request with
# no role header as the owner, so the test HARNESS now authenticates every
# TestClient explicitly as a named owner operator. Per-request headers
# (e.g. X-Role: viewer / staff in the role tests) still override these
# defaults, so every role assertion in Batches 001–007 is exercised
# unchanged. Tests of the deny-by-default behaviour build their clients
# with anonymous_client(), which sends no role and no actor.
HARNESS_HEADERS = {"X-Role": "owner", "X-Actor": "test-operator"}

_orig_init = TestClient.__init__


def _authenticated_init(self, *args, **kwargs):
    _orig_init(self, *args, **kwargs)
    for k, v in HARNESS_HEADERS.items():
        self.headers.setdefault(k, v)


TestClient.__init__ = _authenticated_init


def anonymous_client(app, **kwargs) -> TestClient:
    c = TestClient(app, **kwargs)
    for k in HARNESS_HEADERS:
        c.headers.pop(k, None)
    return c


@pytest.fixture()
def conn():
    c = connect(":memory:")
    yield c
    c.close()
