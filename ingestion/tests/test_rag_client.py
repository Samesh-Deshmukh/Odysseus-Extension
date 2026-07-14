import httpx
import pytest

from ingestion.rag_client import RagClient, RagError


def _client_with_handler(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(base_url="http://brain.test", transport=transport)


def test_login_then_upload_sends_cookie_and_returns_count(tmp_path):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return httpx.Response(200, json={"ok": True},
                                  headers={"set-cookie": "odysseus_session=abc; Path=/"})
        if request.url.path == "/api/personal/upload":
            seen["cookie"] = request.headers.get("cookie", "")
            seen["ct"] = request.headers.get("content-type", "")
            return httpx.Response(200, json={"indexed": 3})
        return httpx.Response(404)

    f = tmp_path / "a.md"
    f.write_text("# hi")
    rc = RagClient("http://brain.test", "sam", "pw", client=_client_with_handler(handler))
    rc.login()
    count = rc.upload(f)

    assert count == 3
    assert "odysseus_session=abc" in seen["cookie"]
    assert seen["ct"].startswith("multipart/form-data")


def test_login_failure_raises():
    def handler(request):
        return httpx.Response(401, json={"error": "bad creds"})

    rc = RagClient("http://brain.test", "sam", "pw", client=_client_with_handler(handler))
    with pytest.raises(RagError):
        rc.login()
