from dataclasses import fields
from datetime import datetime

import pytest

from eml_transformer.ingestion.sources.gdelt import GDELTSource


EXPECTED_TEXT_RECORD_FIELDS = {
    "record_id",
    "source",
    "source_type",
    "title",
    "text",
    "published_at",
    "retrieved_at",
    "url",
    "region",
    "categories",
    "metadata",
    "raw",
}


def make_standardized_gdelt_record(**overrides):
    record = {
        "GKGRECORDID": "20260101000000-0000000000",
        "DATE": "20260101000000",
        "GDELT_TIMESTAMP": "20260101000000",
        "SourceCommonName": "example.com",
        "DocumentIdentifier": "https://example.com/article",
        "Themes": "POWER;GRID;WEATHER",
        "Organizations": "MISO;NWS",
        "Persons": "Jane Doe;John Smith",
        "Locations": "1#Indiana#US#USIN#39.7684#-86.1581",
        "Tone": "-1.25,0.0,2.5,0.5,1.0,0.0",
        "Extras": (
            "<PAGE_TITLE>Major Power Outage Hits Indiana</PAGE_TITLE>"
            "<PAGE_PRECISEPUBTIMESTAMP>20260101123045</PAGE_PRECISEPUBTIMESTAMP>"
        ),
        "theme_match": True,
        "organization_match": True,
        "location_match": True,
        "filter_match_count": 3,
    }

    record.update(overrides)
    return record


def test_standardize_record_returns_expected_core_fields(gdelt_source):
    record = make_standardized_gdelt_record()

    result = gdelt_source.standardize_record(record)

    assert result.record_id == "20260101000000-0000000000"
    assert result.source == gdelt_source.name
    assert result.source_type == gdelt_source.source_type
    assert result.title == "Major Power Outage Hits Indiana"
    assert result.text == ""
    assert result.url == "https://example.com/article"
    assert result.categories == ["POWER", "GRID", "WEATHER"]
    assert result.raw is record


def test_standardize_record_uses_precise_page_timestamp_when_available(gdelt_source):
    record = make_standardized_gdelt_record(
        Extras=(
            "<PAGE_TITLE>Title</PAGE_TITLE>"
            "<PAGE_PRECISEPUBTIMESTAMP>20260101123045</PAGE_PRECISEPUBTIMESTAMP>"
        ),
        GDELT_TIMESTAMP="20260101000000",
        DATE="20260101000000",
    )

    result = gdelt_source.standardize_record(record)

    assert result.published_at.startswith("2026-01-01T12:30:45")
    assert result.metadata["published_at"] == {
        "source": "page_metadata",
        "precision": "second",
    }


def test_standardize_record_falls_back_to_gdelt_timestamp(gdelt_source):
    record = make_standardized_gdelt_record(
        Extras="<PAGE_TITLE>Title</PAGE_TITLE>",
        GDELT_TIMESTAMP="20260101001500",
        DATE="20260101000000",
    )

    result = gdelt_source.standardize_record(record)

    assert result.published_at.startswith("2026-01-01T00:15:00")
    assert result.metadata["published_at"] == {
        "source": "gdelt",
        "precision": "15min",
    }


def test_standardize_record_falls_back_to_date_when_gdelt_timestamp_missing(gdelt_source):
    record = make_standardized_gdelt_record(
        Extras="",
        GDELT_TIMESTAMP=None,
        DATE="20260101003000",
    )

    result = gdelt_source.standardize_record(record)

    assert result.published_at.startswith("2026-01-01T00:30:00")
    assert result.metadata["published_at"] == {
        "source": "gdelt",
        "precision": "15min",
    }


def test_standardize_record_strips_empty_theme_values(gdelt_source):
    record = make_standardized_gdelt_record(
        Themes=" POWER ; ; GRID ; WEATHER ; ",
    )

    result = gdelt_source.standardize_record(record)

    assert result.categories == ["POWER", "GRID", "WEATHER"]


def test_standardize_record_handles_missing_themes(gdelt_source):
    record = make_standardized_gdelt_record(Themes="")

    result = gdelt_source.standardize_record(record)

    assert result.categories == []


def test_standardize_record_parses_organizations(gdelt_source):
    record = make_standardized_gdelt_record(
        Organizations=" MISO ; ; NWS ; DOE ",
    )

    result = gdelt_source.standardize_record(record)

    assert result.metadata["organizations"] == ["MISO", "NWS", "DOE"]


def test_standardize_record_handles_missing_organizations(gdelt_source):
    record = make_standardized_gdelt_record(Organizations="")

    result = gdelt_source.standardize_record(record)

    assert result.metadata["organizations"] == []


def test_standardize_record_parses_persons(gdelt_source):
    record = make_standardized_gdelt_record(
        Persons=" Jane Doe ; ; John Smith ; ",
    )

    result = gdelt_source.standardize_record(record)

    assert result.metadata["persons"] == ["Jane Doe", "John Smith"]


def test_standardize_record_handles_missing_persons(gdelt_source):
    record = make_standardized_gdelt_record(Persons="")

    result = gdelt_source.standardize_record(record)

    assert result.metadata["persons"] == []


def test_standardize_record_parses_locations_and_sets_region(gdelt_source):
    record = make_standardized_gdelt_record(
        Locations=(
            "1#Indiana#US#USIN#39.7684#-86.1581;"
            "1#Illinois#US#USIL#40.6331#-89.3985"
        )
    )

    result = gdelt_source.standardize_record(record)

    assert result.metadata["locations"]
    assert result.region == result.metadata["locations"][0]


def test_standardize_record_sets_region_none_when_no_locations(gdelt_source):
    record = make_standardized_gdelt_record(Locations="")

    result = gdelt_source.standardize_record(record)

    assert result.region is None
    assert result.metadata["locations"] == []


def test_standardize_record_preserves_source_common_name(gdelt_source):
    record = make_standardized_gdelt_record(
        SourceCommonName="utilitydive.com",
    )

    result = gdelt_source.standardize_record(record)

    assert result.metadata["source_common_name"] == "utilitydive.com"


def test_standardize_record_preserves_tone(gdelt_source):
    record = make_standardized_gdelt_record(
        Tone="-3.5,1.0,4.5,0.0,2.0,0.5",
    )

    result = gdelt_source.standardize_record(record)

    assert result.metadata["tone"] == "-3.5,1.0,4.5,0.0,2.0,0.5"


def test_standardize_record_preserves_filter_metadata(gdelt_source):
    record = make_standardized_gdelt_record(
        theme_match=True,
        organization_match=False,
        location_match=True,
        filter_match_count=2,
    )

    result = gdelt_source.standardize_record(record)

    assert result.metadata["filter"] == {
        "theme_match": True,
        "organization_match": False,
        "location_match": True,
        "match_count": 2,
    }


def test_standardize_record_handles_missing_filter_metadata(gdelt_source):
    record = make_standardized_gdelt_record(
        theme_match=None,
        organization_match=None,
        location_match=None,
        filter_match_count=None,
    )

    result = gdelt_source.standardize_record(record)

    assert result.metadata["filter"] == {
        "theme_match": None,
        "organization_match": None,
        "location_match": None,
        "match_count": None,
    }


def test_standardize_record_handles_missing_title(gdelt_source):
    record = make_standardized_gdelt_record(
        Extras="<PAGE_PRECISEPUBTIMESTAMP>20260101123045</PAGE_PRECISEPUBTIMESTAMP>",
    )

    result = gdelt_source.standardize_record(record)

    assert result.title == ""


def test_standardize_record_handles_missing_extras(gdelt_source):
    record = make_standardized_gdelt_record()
    record.pop("Extras")

    result = gdelt_source.standardize_record(record)

    assert result.title == ""
    assert result.metadata["published_at"] == {
        "source": "gdelt",
        "precision": "15min",
    }


def test_standardize_record_handles_missing_document_identifier(gdelt_source):
    record = make_standardized_gdelt_record(DocumentIdentifier=None)

    result = gdelt_source.standardize_record(record)

    assert result.url is None


def test_standardize_record_casts_record_id_to_string(gdelt_source):
    record = make_standardized_gdelt_record(GKGRECORDID=12345)

    result = gdelt_source.standardize_record(record)

    assert result.record_id == "12345"


def test_standardize_record_requires_gkg_record_id(gdelt_source):
    record = make_standardized_gdelt_record()
    record.pop("GKGRECORDID")

    with pytest.raises(KeyError):
        gdelt_source.standardize_record(record)


def test_standardize_record_retrieved_at_is_valid_iso_timestamp(gdelt_source):
    record = make_standardized_gdelt_record()

    result = gdelt_source.standardize_record(record)

    parsed = datetime.fromisoformat(result.retrieved_at)

    assert parsed.tzinfo is not None


def test_standardize_record_returns_complete_text_record(gdelt_source):
    record = make_standardized_gdelt_record()

    result = gdelt_source.standardize_record(record)

    actual_fields = {field.name for field in fields(type(result))}

    assert actual_fields == EXPECTED_TEXT_RECORD_FIELDS