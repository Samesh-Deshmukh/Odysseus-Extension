from __future__ import annotations

import mimetypes
from pathlib import Path

import httpx


class RagError(Exception):
    pass


class RagClient:
    def __init__(self, base_url, user, password, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.password = password
        self.client = client or httpx.Client(base_url=self.base_url, timeout=60.0)

    def health(self) -> bool:
        try:
            resp = self.client.get("/")
        except httpx.HTTPError:
            return False
        return resp.status_code < 400

    def login(self) -> None:
        resp = self.client.post(
            "/api/auth/login",
            json={"username": self.user, "password": self.password},
        )
        if resp.status_code >= 400:
            raise RagError(f"login failed: {resp.status_code} {resp.text[:200]}")

    def upload(self, path: Path) -> int:
        path = Path(path)
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with open(path, "rb") as fh:
            files = {"files": (path.name, fh, ctype)}
            resp = self.client.post("/api/personal/upload", files=files)
        if resp.status_code >= 400:
            raise RagError(f"upload failed for {path.name}: {resp.status_code} {resp.text[:200]}")
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        return int(data.get("indexed", data.get("total_indexed", 0)))
