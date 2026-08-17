from __future__ import annotations

from typing import Any

class FakeScraper:
    def __init__(self, result: dict[str, Any] | None = None, exc: Exception | None = None):
        self.result = result or {}
        self.exc = exc
        self.urls_seen: list[str] = []

    async def scrape(self, session, url: str) -> dict[str, Any]:
        self.urls_seen.append(url)

        if self.exc:
            raise self.exc

        return self.result
