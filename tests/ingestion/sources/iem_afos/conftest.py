from collections.abc import Callable
from typing import Any
from pathlib import Path

import pytest

from eml_transformer.ingestion.sources.iem_afos import (
    IEMAFOSSource,
)


EXAMPLES_DIR = Path(__file__).parent / "iem_text_examples"




class FakeResponse:
    def __init__(
        self,
        text: str = "AFOS response text",
        error: Exception | None = None,
    ) -> None:
        self.text = text
        self.error = error
        self.raise_for_status_called = False

    def raise_for_status(self) -> None:
        self.raise_for_status_called = True

        if self.error is not None:
            raise self.error


class FakeSession:
    def __init__(
        self,
        response: FakeResponse,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def get(
        self,
        url: str,
        params: dict[str, Any],
        timeout: int,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "params": params,
                "timeout": timeout,
            }
        )

        if self.error is not None:
            raise self.error

        return self.response


@pytest.fixture
def fake_response() -> FakeResponse:
    return FakeResponse()


@pytest.fixture
def fake_session(
    fake_response: FakeResponse,
) -> FakeSession:
    return FakeSession(response=fake_response)


@pytest.fixture
def iem_source(
    fake_session: FakeSession,
) -> IEMAFOSSource:
    return IEMAFOSSource(
        wfos=["IND"],
        product_types=["AFD"],
        session=fake_session,
        sleep_fn=lambda _: None,
        request_delay=(0, 0),
        limit=100,
        fmt="text",
        timeout=15,
    )

@pytest.fixture
def load_iem_text() -> Callable[[str], str]:
    def load(filename: str) -> str:
        return (EXAMPLES_DIR / filename).read_text(
            encoding="utf-8"
        )

    return load

