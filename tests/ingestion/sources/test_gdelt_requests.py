import zipfile
from io import BytesIO

import pandas as pd
import pytest
import requests

from eml_transformer.ingestion.sources.gdelt import GDELTSource, GKG_COLUMNS


GDELT_URL = (
    "http://data.gdeltproject.org/gdeltv2/"
    "20260101000000.gkg.csv.zip"
)


def make_gkg_row(
    record_id: str = "gdelt-1",
    timestamp: str = "20260101000000",
    themes: str = "POWER;GRID",
    v2_locations: str = "2#Indiana#US#IN#39#-86#IN",
    organizations: str = "",
    v2_organizations: str = "",
    url: str = "https://example.com/a",
) -> list[str]:
    return [
        record_id,
        timestamp,
        "",
        "example.com",
        url,
        "",
        "",
        themes,
        "",
        "",
        v2_locations,
        "",
        "",
        organizations,
        v2_organizations,
        "0",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]


def make_gkg_zip(rows: list[list[str]]) -> bytes:
    buffer = BytesIO()

    content = "\n".join(
        "\t".join(row)
        for row in rows
    )

    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("test.gkg.csv", content)

    return buffer.getvalue()


class FakeResponse:
    def __init__(self, content: bytes = b"", status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


def test_load_gkg_file_reads_zip_and_filters_records(monkeypatch):
    source = GDELTSource(
        target_themes={"POWER", "GRID"},
        target_locations={"US-IN"},
        target_organizations={"MISO"},
        min_filter_matches=2,
    )

    zip_bytes = make_gkg_zip(
        [
            make_gkg_row(
                record_id="gdelt-1",
                themes="POWER;GRID",
                v2_locations="2#Indiana#US#IN#39#-86#IN",
            )
        ]
    )

    def fake_get(url, timeout):
        assert url == GDELT_URL
        assert timeout == 60
        return FakeResponse(zip_bytes)

    monkeypatch.setattr(
        "eml_transformer.ingestion.sources.gdelt.requests.get",
        fake_get,
    )

    result, total_records = source._load_gkg_file("20260101000000")

    assert total_records == 1
    assert len(result) == 1
    assert result.iloc[0]["GKGRECORDID"] == "gdelt-1"
    assert result.iloc[0]["GDELT_TIMESTAMP"] == "20260101000000"
    assert result.iloc[0]["GDELT_URL"] == GDELT_URL


def test_load_gkg_file_counts_all_records_even_if_filtered(monkeypatch):
    source = GDELTSource(
        target_themes={"POWER"},
        target_locations={"US-IN"},
        min_filter_matches=1,
    )

    rows = [
        make_gkg_row(
            record_id="keep-1",
            themes="POWER",
            v2_locations="2#Indiana#US#IN#39#-86#IN",
        ),
        make_gkg_row(
            record_id="drop-1",
            themes="SPORTS",
            v2_locations="2#California#US#CA#36#-119#CA",
        ),
    ]

    zip_bytes = make_gkg_zip(rows)

    monkeypatch.setattr(
        "eml_transformer.ingestion.sources.gdelt.requests.get",
        lambda url, timeout: FakeResponse(zip_bytes),
    )

    result, total_records = source._load_gkg_file("20260101000000")

    assert total_records == 2
    assert len(result) == 1
    assert result.iloc[0]["GKGRECORDID"] == "keep-1"


def test_load_gkg_file_returns_empty_dataframe_when_no_records_match(monkeypatch):
    source = GDELTSource(
        target_themes={"POWER"},
        target_locations={"US-IN"},
        min_filter_matches=2,
    )

    zip_bytes = make_gkg_zip(
        [
            make_gkg_row(
                record_id="drop-1",
                themes="SPORTS",
                v2_locations="2#California#US#CA#36#-119#CA",
            )
        ]
    )

    monkeypatch.setattr(
        "eml_transformer.ingestion.sources.gdelt.requests.get",
        lambda url, timeout: FakeResponse(zip_bytes),
    )

    result, total_records = source._load_gkg_file("20260101000000")

    assert total_records == 1
    assert result.empty


def test_load_gkg_file_returns_none_when_download_raises(monkeypatch):
    source = GDELTSource()

    def fake_get(url, timeout):
        raise RuntimeError("network failed")

    monkeypatch.setattr(
        "eml_transformer.ingestion.sources.gdelt.requests.get",
        fake_get,
    )

    result, total_records = source._load_gkg_file("20260101000000")

    assert result is None
    assert total_records == 0


def test_load_gkg_file_returns_none_on_404(monkeypatch):
    source = GDELTSource()

    monkeypatch.setattr(
        "eml_transformer.ingestion.sources.gdelt.requests.get",
        lambda url, timeout: FakeResponse(status_code=404),
    )

    result, total_records = source._load_gkg_file("20260101000000")

    assert result is None
    assert total_records == 0


def test_load_gkg_file_returns_none_on_timeout(monkeypatch):
    source = GDELTSource()

    def fake_get(url, timeout):
        raise requests.Timeout("request timed out")

    monkeypatch.setattr(
        "eml_transformer.ingestion.sources.gdelt.requests.get",
        fake_get,
    )

    result, total_records = source._load_gkg_file("20260101000000")

    assert result is None
    assert total_records == 0


def test_load_gkg_file_returns_none_on_connection_error(monkeypatch):
    source = GDELTSource()

    def fake_get(url, timeout):
        raise requests.ConnectionError("connection failed")

    monkeypatch.setattr(
        "eml_transformer.ingestion.sources.gdelt.requests.get",
        fake_get,
    )

    result, total_records = source._load_gkg_file("20260101000000")

    assert result is None
    assert total_records == 0


def test_load_gkg_file_returns_none_on_corrupt_zip(monkeypatch):
    source = GDELTSource()

    monkeypatch.setattr(
        "eml_transformer.ingestion.sources.gdelt.requests.get",
        lambda url, timeout: FakeResponse(b"this is not a zip file"),
    )

    result, total_records = source._load_gkg_file("20260101000000")

    assert result is None
    assert total_records == 0


def test_load_gkg_file_handles_empty_zip_file(monkeypatch):
    source = GDELTSource()

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w"):
        pass

    monkeypatch.setattr(
        "eml_transformer.ingestion.sources.gdelt.requests.get",
        lambda url, timeout: FakeResponse(buffer.getvalue()),
    )

    result, total_records = source._load_gkg_file("20260101000000")

    assert result is None
    assert total_records == 0


def test_load_gkg_file_handles_empty_gkg_content(monkeypatch):
    source = GDELTSource()

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("test.gkg.csv", "")

    monkeypatch.setattr(
        "eml_transformer.ingestion.sources.gdelt.requests.get",
        lambda url, timeout: FakeResponse(buffer.getvalue()),
    )

    result, total_records = source._load_gkg_file("20260101000000")

    assert result is None or result.empty
    assert total_records == 0


def test_get_records_combines_loaded_files(monkeypatch):
    source = GDELTSource()

    def fake_load_gkg_file(timestamp):
        return (
            pd.DataFrame(
                [
                    {
                        "GKGRECORDID": f"record-{timestamp}",
                        "GDELT_TIMESTAMP": timestamp,
                    }
                ]
            ),
            10,
        )

    monkeypatch.setattr(source, "_load_gkg_file", fake_load_gkg_file)

    result, total_records = source._get_records(
        [
            "20260101000000",
            "20260101001500",
        ]
    )

    assert total_records == 20
    assert len(result) == 2
    assert set(result["GKGRECORDID"]) == {
        "record-20260101000000",
        "record-20260101001500",
    }


def test_get_records_combines_multiple_rows_per_file(monkeypatch):
    source = GDELTSource()

    def fake_load_gkg_file(timestamp):
        return (
            pd.DataFrame(
                [
                    {
                        "GKGRECORDID": f"{timestamp}-1",
                        "GDELT_TIMESTAMP": timestamp,
                    },
                    {
                        "GKGRECORDID": f"{timestamp}-2",
                        "GDELT_TIMESTAMP": timestamp,
                    },
                ]
            ),
            20,
        )

    monkeypatch.setattr(source, "_load_gkg_file", fake_load_gkg_file)

    result, total_records = source._get_records(
        [
            "20260101000000",
            "20260101001500",
        ]
    )

    assert total_records == 40
    assert len(result) == 4
    assert set(result["GKG_TIMESTAMP"] if "GKG_TIMESTAMP" in result.columns else result["GDELT_TIMESTAMP"]) == {
        "20260101000000",
        "20260101001500",
    }


def test_get_records_returns_empty_dataframe_when_all_files_empty(monkeypatch):
    source = GDELTSource()

    def fake_load_gkg_file(timestamp):
        return pd.DataFrame(), 100

    monkeypatch.setattr(source, "_load_gkg_file", fake_load_gkg_file)

    result, total_records = source._get_records(
        [
            "20260101000000",
            "20260101001500",
        ]
    )

    assert total_records == 200
    assert result.empty


def test_get_records_skips_none_results(monkeypatch):
    source = GDELTSource()

    def fake_load_gkg_file(timestamp):
        return None, 0

    monkeypatch.setattr(source, "_load_gkg_file", fake_load_gkg_file)

    result, total_records = source._get_records(
        [
            "20260101000000",
            "20260101001500",
        ]
    )

    assert total_records == 0
    assert result.empty


def test_get_records_combines_successful_and_empty_files(monkeypatch):
    source = GDELTSource()

    def fake_load_gkg_file(timestamp):
        if timestamp == "20260101001500":
            return pd.DataFrame(), 50

        return (
            pd.DataFrame(
                [
                    {
                        "GKGRECORDID": f"record-{timestamp}",
                        "GDELT_TIMESTAMP": timestamp,
                    }
                ]
            ),
            100,
        )

    monkeypatch.setattr(source, "_load_gkg_file", fake_load_gkg_file)

    result, total_records = source._get_records(
        [
            "20260101000000",
            "20260101001500",
            "20260101003000",
        ]
    )

    assert total_records == 250
    assert len(result) == 2
    assert set(result["GKGRECORDID"]) == {
        "record-20260101000000",
        "record-20260101003000",
    }


def test_get_records_continues_when_one_file_raises(monkeypatch):
    source = GDELTSource()

    def fake_load_gkg_file(timestamp):
        if timestamp == "20260101001500":
            raise RuntimeError("download failed")

        return (
            pd.DataFrame(
                [
                    {
                        "GKGRECORDID": f"record-{timestamp}",
                        "GDELT_TIMESTAMP": timestamp,
                    }
                ]
            ),
            10,
        )

    monkeypatch.setattr(source, "_load_gkg_file", fake_load_gkg_file)

    result, total_records = source._get_records(
        [
            "20260101000000",
            "20260101001500",
            "20260101003000",
        ]
    )

    assert total_records == 20
    assert len(result) == 2
    assert "record-20260101001500" not in set(result["GKGRECORDID"])


def test_get_records_returns_empty_dataframe_when_all_files_fail(monkeypatch):
    source = GDELTSource()

    def fake_load_gkg_file(timestamp):
        raise RuntimeError("download failed")

    monkeypatch.setattr(source, "_load_gkg_file", fake_load_gkg_file)

    result, total_records = source._get_records(
        [
            "20260101000000",
            "20260101001500",
        ]
    )

    assert total_records == 0
    assert result.empty
    assert list(result.columns) == GKG_COLUMNS


def test_get_records_empty_timestamp_list_returns_empty_dataframe():
    source = GDELTSource()

    result, total_records = source._get_records([])

    assert total_records == 0
    assert result.empty
    assert list(result.columns) == GKG_COLUMNS