from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

import pytest


FIXTURE_DIR = Path(__file__).parent / "iem_text_examples"


def load_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


FIXTURES = [
    ("afdind_standard.txt", "AFDIND"),
    ("afdind_two_entries.txt", "AFDIND"),
    ("afdind_three_entries.txt", "AFDIND"),
    ("afdiwx_standard.txt", "AFDIWX"),
    ("hwoind_standard.txt", "HWOIND"),
    ("lsrind_standard.txt", "LSRIND"),
    ("npwind_standard.txt", "NPWIND"),
    ("spsind_standard.txt", "SPSIND"),
    ("wswind_standard.txt", "WSWIND"),
]


@pytest.mark.parametrize(("filename", "expected_pil"), FIXTURES)
def test_real_iem_examples_parse_without_crashing(
    iem_source,
    filename,
    expected_pil,
):
    text = load_text(filename)

    records = iem_source._parse_response_item(
        {
            "pil": expected_pil,
            "response": text,
        }
    )

    assert isinstance(records, list)
    assert records

    for record in records:
        assert record["source_id"]
        assert record["pil"] == expected_pil
        assert record["raw_text"]
        assert record["issued_at_text"]
        assert record["published_at"]
        assert record["header"]


@pytest.mark.parametrize(
    ("filename", "expected_count"),
    [
        ("afdind_standard.txt", 1),
        ("afdind_two_entries.txt", 2),
        ("afdind_three_entries.txt", 3),
    ],
)
def test_split_and_parse_multiple_entries(
    iem_source,
    filename,
    expected_count,
):
    text = load_text(filename)

    records = iem_source._parse_response_item(
        {
            "pil": "AFDIND",
            "response": text,
        }
    )

    assert len(records) == expected_count


def test_parse_product_chunk_standard_afd(iem_source):
    text = load_text("afdind_standard.txt")

    record = iem_source._parse_product_chunk(
        chunk=text,
        fallback_pil="AFDIND",
    )

    assert record["source_id"]
    assert record["pil"] == "AFDIND"
    assert record["published_at"]
    assert record["issued_at_text"]
    assert record["raw_text"] == text.strip()

    assert record["header"]["office"] == "KIND"
    assert record["header"]["wmo"] == "FXUS63"
    assert record["header"]["pil"] == "AFDIND"


def test_parse_product_chunk_uses_header_pil_over_fallback(iem_source):
    text = load_text("afdind_standard.txt")

    record = iem_source._parse_product_chunk(
        chunk=text,
        fallback_pil="AFDIWX",
    )

    assert record["pil"] == "AFDIND"


def test_parse_product_chunk_raises_for_missing_timestamp(iem_source):
    text = """
000 FXUS63 KIND 011945
AFDIND

Area Forecast Discussion
National Weather Service Indianapolis IN

.KEY MESSAGES...
- Cold conditions expected.

$$
""".strip()

    with pytest.raises(ValueError, match="Missing issuance timestamp"):
        iem_source._parse_product_chunk(
            chunk=text,
            fallback_pil="AFDIND",
        )


def test_parse_header(iem_source):
    text = load_text("afdind_standard.txt")

    result = iem_source._parse_header(text)

    assert result == {
        "raw_id": result["raw_id"],
        "wmo": "FXUS63",
        "wmo_header": (
            f"FXUS63 KIND {result['issued_code']}"
        ),
        "office": "KIND",
        "issued_code": result["issued_code"],
        "pil": "AFDIND",
    }

    assert result["raw_id"] is not None
    assert result["issued_code"] is not None


def test_parse_header_returns_empty_header_when_missing(iem_source):
    result = iem_source._parse_header(
        "This text does not contain an AFOS header."
    )

    assert result == {
        "raw_id": None,
        "wmo": None,
        "wmo_header": None,
        "office": None,
        "issued_code": None,
        "pil": None,
    }


def test_parse_sections(iem_source):
    text = load_text("afdind_standard.txt")

    sections = iem_source._parse_sections(text)

    assert len(sections) == 4
    assert sorted(sections) == [
        "AVIATION",
        "DISCUSSION",
        "IND WATCHES/WARNINGS/ADVISORIES",
        "KEY MESSAGES",
    ]

    discussion = sections["DISCUSSION"]
    assert discussion.name == "DISCUSSION"
    assert discussion.detail == "This evening through Thursday"
    assert discussion.text

    aviation = sections["AVIATION"]
    assert aviation.name == "AVIATION"
    assert aviation.detail == "18Z TAF Issuance"
    assert aviation.text

    key_messages = sections["KEY MESSAGES"]
    assert key_messages.name == "KEY MESSAGES"
    assert key_messages.detail is None
    assert key_messages.text

    advisories = sections[
        "IND WATCHES/WARNINGS/ADVISORIES"
    ]
    assert advisories.name == (
        "IND WATCHES/WARNINGS/ADVISORIES"
    )
    assert advisories.detail is None
    assert advisories.text == "None."


def test_parse_sections_returns_parsed_section_objects(iem_source):
    text = load_text("afdind_standard.txt")

    sections = iem_source._parse_sections(text)

    for name, section in sections.items():
        assert section.name == name
        assert isinstance(section.text, str)
        assert section.text


def test_parse_sections_removes_issued_at_line(iem_source):
    text = """
.SHORT TERM (Tonight through Friday)...
Issued at 300 PM EST Thu Jan 1 2026

Snow is expected tonight.

&&
""".strip()

    sections = iem_source._parse_sections(text)
    section = sections["SHORT TERM"]

    assert section.detail == "Tonight through Friday"
    assert section.issued_at_text == (
        "Issued at 300 PM EST Thu Jan 1 2026"
    )
    assert section.text == "Snow is expected tonight."
    assert "Issued at" not in section.text


def test_parse_sections_returns_empty_dictionary_when_absent(
    iem_source,
):
    sections = iem_source._parse_sections(
        "Product without any formatted sections."
    )

    assert sections == {}


def test_parse_published_at(iem_source):
    text = load_text("afdind_standard.txt")

    issued_at_text, published_at = (
        iem_source._parse_published_at(
            raw_text=text,
            pil="AFDIND",
        )
    )

    parsed_datetime = datetime.fromisoformat(published_at)

    
    assert issued_at_text
    assert issued_at_text.startswith("Issued at")
    assert parsed_datetime.tzinfo is not None
    
    expected_local = datetime(
        2026,
        7,
        9,
        14,
        38,
        tzinfo=ZoneInfo("America/Detroit"),
    )
    expected_utc = expected_local.astimezone(timezone.utc)

    assert parsed_datetime == expected_utc


def test_parse_published_at_is_normalized_to_utc(iem_source):
    text = load_text("afdind_standard.txt")

    _, published_at = iem_source._parse_published_at(
        raw_text=text,
        pil="AFDIND",
    )

    parsed_datetime = datetime.fromisoformat(published_at)

    assert parsed_datetime.utcoffset().total_seconds() == 0


def test_parse_published_at_raises_when_timestamp_is_missing(
    iem_source,
):
    with pytest.raises(
        ValueError,
        match="Missing issuance timestamp for PIL=AFDIND",
    ):
        iem_source._parse_published_at(
            raw_text="No issuance timestamp is present.",
            pil="AFDIND",
        )


def test_source_id_is_deterministic(iem_source):
    text = load_text("afdind_standard.txt")

    first = iem_source._parse_product_chunk(
        chunk=text,
        fallback_pil="AFDIND",
    )
    second = iem_source._parse_product_chunk(
        chunk=text,
        fallback_pil="AFDIND",
    )

    assert first["source_id"] == second["source_id"]


def test_parse_records_removes_duplicate_products(iem_source):
    text = load_text("afdind_standard.txt")

    records = iem_source._parse_records(
        [
            {
                "pil": "AFDIND",
                "response": text,
            },
            {
                "pil": "AFDIND",
                "response": text,
            },
        ]
    )

    assert len(records) == 1


def test_published_at(iem_source): 


    text = load_text('missing_published_at_1.txt')

    issued_at_text, published_at = (
        iem_source._parse_published_at(
            raw_text=text,
            pil="HWOILX",
        )
    )

    print(published_at)
    assert published_at

