import zipfile
from io import BytesIO

import pandas as pd

from eml_transformer.ingestion.sources.gdelt import GDELTSource


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
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        pass


def test_load_gkg_file_reads_zip_and_filters_records(monkeypatch):
    source = GDELTSource(
        target_themes={"POWER", "GRID"},
        target_locations={"US-IN"},
        target_organizations={"MISO"},
        min_filter_matches=2,
    )

    row = [
        "gdelt-1",                  # GKGRECORDID
        "20260101000000",           # DATE
        "",                         # SourceCollectionIdentifier
        "example.com",              # SourceCommonName
        "https://example.com/a",     # DocumentIdentifier
        "",                         # Counts
        "",                         # V2Counts
        "POWER;GRID",               # Themes
        "",                         # V2Themes
        "",                         # Locations
        "2#Indiana#US#IN#39#-86#IN", # V2Locations
        "",                         # Persons
        "",                         # V2Persons
        "",                         # Organizations
        "",                         # V2Organizations
        "0",                        # Tone
        "", "", "", "", "", "", "", "", "", "", ""
    ]

    zip_bytes = make_gkg_zip([row])

    def fake_get(url, timeout):
        assert url == "http://data.gdeltproject.org/gdeltv2/20260101000000.gkg.csv.zip"
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
    assert result.iloc[0]["GDELT_URL"] == (
        "http://data.gdeltproject.org/gdeltv2/20260101000000.gkg.csv.zip"
    )

def test_load_gkg_file_returns_none_when_download_fails(monkeypatch):
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

    monkeypatch.setattr(
        source,
        "_load_gkg_file",
        fake_load_gkg_file,
    )

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