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


def test_fetch_file_reads_filters_and_adds_metadata(monkeypatch):
    source = GDELTSource(
        target_themes={"POWER", "GRID"},
        target_locations={"US-IN"},
        target_organizations={"MISO"},
        min_theme_matches=2,
    )

    zip_bytes = make_gkg_zip(
        [
            make_gkg_row(
                record_id="gdelt-1",
                themes="POWER;GRID",
                v2_locations=(
                    "2#Indiana#US#IN#39#-86#IN"
                ),
            )
        ]
    )

    def fake_get(url, timeout):
        assert url == GDELT_URL
        assert timeout == source.timeout
        return FakeResponse(zip_bytes)

    monkeypatch.setattr(
        source._session,
        "get",
        fake_get,
    )

    result, total_records = source._fetch_file(
        "20260101000000"
    )

    assert total_records == 1
    assert len(result) == 1
    assert result.iloc[0]["GKGRECORDID"] == "gdelt-1"
    assert (
        result.iloc[0]["GDELT_TIMESTAMP"]
        == "20260101000000"
    )
    assert result.iloc[0]["GDELT_URL"] == GDELT_URL


def test_fetch_file_counts_rows_before_filtering(monkeypatch):
    source = GDELTSource(
        target_themes={"POWER"},
        target_locations={"US-IN"},
        min_theme_matches=1,
    )

    zip_bytes = make_gkg_zip(
        [
            make_gkg_row(
                record_id="keep-1",
                themes="POWER",
                v2_locations=(
                    "2#Indiana#US#IN#39#-86#IN"
                ),
            ),
            make_gkg_row(
                record_id="drop-1",
                themes="SPORTS",
                v2_locations=(
                    "2#California#US#CA#36#-119#CA"
                ),
            ),
        ]
    )

    monkeypatch.setattr(
        source._session,
        "get",
        lambda url, timeout: FakeResponse(zip_bytes),
    )

    result, total_records = source._fetch_file(
        "20260101000000"
    )

    assert total_records == 2
    assert len(result) == 1
    assert result.iloc[0]["GKGRECORDID"] == "keep-1"


def test_fetch_file_returns_empty_frame_when_nothing_matches(
    monkeypatch,
):
    source = GDELTSource(
        target_themes={"POWER"},
        target_locations={"US-IN"},
        min_theme_matches=2,
    )

    zip_bytes = make_gkg_zip(
        [
            make_gkg_row(
                record_id="drop-1",
                themes="SPORTS",
                v2_locations=(
                    "2#California#US#CA#36#-119#CA"
                ),
            )
        ]
    )

    monkeypatch.setattr(
        source._session,
        "get",
        lambda url, timeout: FakeResponse(zip_bytes),
    )

    result, total_records = source._fetch_file(
        "20260101000000"
    )

    assert total_records == 1
    assert result.empty


def test_fetch_file_counts_rows_before_filtering(monkeypatch):
    source = GDELTSource(
        target_themes={"POWER"},
        target_locations={"US-IN"},
        min_theme_matches=1,
    )

    zip_bytes = make_gkg_zip(
        [
            make_gkg_row(
                record_id="keep-1",
                themes="POWER",
                v2_locations=(
                    "2#Indiana#US#IN#39#-86#IN"
                ),
            ),
            make_gkg_row(
                record_id="drop-1",
                themes="SPORTS",
                v2_locations=(
                    "2#California#US#CA#36#-119#CA"
                ),
            ),
        ]
    )

    monkeypatch.setattr(
        source._session,
        "get",
        lambda url, timeout: FakeResponse(zip_bytes),
    )

    result, total_records = source._fetch_file(
        "20260101000000"
    )

    assert total_records == 2
    assert len(result) == 1
    assert result.iloc[0]["GKGRECORDID"] == "keep-1"


def test_fetch_file_returns_empty_frame_when_nothing_matches(
    monkeypatch,
):
    source = GDELTSource(
        target_themes={"POWER"},
        target_locations={"US-IN"},
        min_theme_matches=2,
    )

    zip_bytes = make_gkg_zip(
        [
            make_gkg_row(
                record_id="drop-1",
                themes="SPORTS",
                v2_locations=(
                    "2#California#US#CA#36#-119#CA"
                ),
            )
        ]
    )

    monkeypatch.setattr(
        source._session,
        "get",
        lambda url, timeout: FakeResponse(zip_bytes),
    )

    result, total_records = source._fetch_file(
        "20260101000000"
    )

    assert total_records == 1
    assert result.empty

@pytest.mark.parametrize(
    ("exception", "expected_type"),
    [
        (
            requests.Timeout("request timed out"),
            requests.Timeout,
        ),
        (
            requests.ConnectionError(
                "connection failed"
            ),
            requests.ConnectionError,
        ),
        (
            RuntimeError("network failed"),
            RuntimeError,
        ),
    ],
)
def test_fetch_file_propagates_download_errors(
    monkeypatch,
    exception,
    expected_type,
):
    source = GDELTSource()

    def fake_get(url, timeout):
        raise exception

    monkeypatch.setattr(
        source._session,
        "get",
        fake_get,
    )

    with pytest.raises(expected_type):
        source._fetch_file("20260101000000")

def test_read_gkg_archive_raises_for_corrupt_zip():
    with pytest.raises(zipfile.BadZipFile):
        GDELTSource._read_gkg_archive(
            b"this is not a zip file"
        )


def test_read_gkg_archive_raises_for_empty_zip():
    buffer = BytesIO()

    with zipfile.ZipFile(buffer, "w"):
        pass

    with pytest.raises(
        ValueError,
        match="contains no files",
    ):
        GDELTSource._read_gkg_archive(
            buffer.getvalue()
        )


def test_read_gkg_archive_reads_rows():
    content = make_gkg_zip(
        [
            make_gkg_row(record_id="gdelt-1"),
            make_gkg_row(record_id="gdelt-2"),
        ]
    )

    result = GDELTSource._read_gkg_archive(content)

    assert len(result) == 2
    assert list(result.columns) == GKG_COLUMNS
    assert result["GKGRECORDID"].tolist() == [
        "gdelt-1",
        "gdelt-2",
    ]


def test_read_gkg_archive_rejects_extra_columns():
    row = make_gkg_row()
    row.append("unexpected")

    content = make_gkg_zip([row])

    with pytest.raises(
        ValueError,
        match="more columns than expected",
    ):
        GDELTSource._read_gkg_archive(content)

def test_read_gkg_archive_raises_for_empty_csv():
    buffer = BytesIO()

    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("test.gkg.csv", "")

    with pytest.raises(pd.errors.EmptyDataError):
        GDELTSource._read_gkg_archive(
            buffer.getvalue()
        )

def test_fetch_files_collects_successful_frames(
    monkeypatch,
):
    source = GDELTSource(max_workers=2)

    def fake_fetch_file(timestamp):
        return (
            pd.DataFrame(
                [
                    {
                        "GKGRECORDID": (
                            f"record-{timestamp}"
                        ),
                        "GDELT_TIMESTAMP": timestamp,
                    }
                ]
            ),
            10,
        )

    monkeypatch.setattr(
        source,
        "_fetch_file",
        fake_fetch_file,
    )

    frames, total_records = source._fetch_files(
        [
            "20260101000000",
            "20260101001500",
        ]
    )

    result = pd.concat(frames, ignore_index=True)

    assert total_records == 20
    assert len(frames) == 2
    assert len(result) == 2
    assert set(result["GKGRECORDID"]) == {
        "record-20260101000000",
        "record-20260101001500",
    }

def test_fetch_files_omits_empty_frames(
    monkeypatch,
):
    source = GDELTSource(max_workers=2)

    monkeypatch.setattr(
        source,
        "_fetch_file",
        lambda timestamp: (pd.DataFrame(), 100),
    )

    frames, total_records = source._fetch_files(
        [
            "20260101000000",
            "20260101001500",
        ]
    )

    assert frames == []
    assert total_records == 200

def test_fetch_files_continues_when_one_file_fails(
    monkeypatch,
):
    source = GDELTSource(max_workers=3)

    def fake_fetch_file(timestamp):
        if timestamp == "20260101001500":
            raise RuntimeError("download failed")

        return (
            pd.DataFrame(
                [
                    {
                        "GKGRECORDID": (
                            f"record-{timestamp}"
                        )
                    }
                ]
            ),
            10,
        )

    monkeypatch.setattr(
        source,
        "_fetch_file",
        fake_fetch_file,
    )

    frames, total_records = source._fetch_files(
        [
            "20260101000000",
            "20260101001500",
            "20260101003000",
        ]
    )

    result = pd.concat(frames, ignore_index=True)

    assert total_records == 20
    assert len(frames) == 2
    assert set(result["GKGRECORDID"]) == {
        "record-20260101000000",
        "record-20260101003000",
    }

def test_fetch_files_returns_empty_list_when_all_fail(
    monkeypatch,
):
    source = GDELTSource(max_workers=2)

    def fake_fetch_file(timestamp):
        raise RuntimeError("download failed")

    monkeypatch.setattr(
        source,
        "_fetch_file",
        fake_fetch_file,
    )

    frames, total_records = source._fetch_files(
        [
            "20260101000000",
            "20260101001500",
        ]
    )

    assert frames == []
    assert total_records == 0


def test_fetch_files_returns_early_for_no_timestamps():
    source = GDELTSource()

    frames, total_records = source._fetch_files([])

    assert frames == []
    assert total_records == 0