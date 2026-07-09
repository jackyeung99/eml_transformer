
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
def test_real_iem_examples_parse_without_crashing(iem_source, filename, expected_pil):
    text = load_text(filename)

    records = iem_source._parse_response_item({
        "pil": expected_pil,
        "response": text,
    })

    assert isinstance(records, list)
    assert len(records) > 0
    assert all(record["pil"] == expected_pil for record in records)
    assert all(record["raw_text"] for record in records)
    assert all(record["published_at"] for record in records)

@pytest.mark.parametrize(
    ("filename", "expected_count"),
    [
        ("afdind_standard.txt", 1),
        ("afdind_two_entries.txt", 2),
        ("afdind_three_entries.txt", 3),
    ],
)
def test_split_and_parse_multiple_entries(iem_source, filename, expected_count):
    text = load_text(filename)

    records = iem_source._parse_response_item({
        "pil": "AFDIND",
        "response": text,
    })

    assert len(records) == expected_count


def test_parse_product_chunk_standard_afd(iem_source):
    text = load_text("afdind_standard.txt")

    record = iem_source._parse_product_chunk(
        chunk=text,
        fallback_pil="AFDIND",
    )

    assert record is not None
    assert record["pil"] == "AFDIND"
    assert record["published_at"] is not None
    assert record["issued_at_text"]
    assert record["header"]["office"] == "KIND"
    assert record["header"]["wmo"] == "FXUS63"

def test_parse_header(iem_source):
    text = load_text("afdind_standard.txt")

    result = iem_source._parse_header(text)

    assert result["raw_id"] is not None
    assert result["wmo"] == "FXUS63"
    assert result["office"] == "KIND"
    assert result["pil"] == "AFDIND"



def test_parse_sections(iem_source):
    text = load_text("afdind_standard.txt")

    result = iem_source._parse_sections(text)

    assert len(result) == 4
    assert sorted(result.keys()) == [
        "AVIATION",
        "DISCUSSION",
        "IND WATCHES/WARNINGS/ADVISORIES",
        "KEY MESSAGES",
    ]

    # Discussion
    assert result["DISCUSSION"]["detail"] == "This evening through Thursday"

    # Aviation
    assert result["AVIATION"]["detail"] == "18Z TAF Issuance"
    # assert result["AVIATION"]["text"].startswith("Impacts:")

    # No parenthetical title
    assert result["KEY MESSAGES"]["detail"] is None
    # assert result["KEY MESSAGES"]["text"].startswith("- Strong to severe storms")

    # No parenthetical title
    assert result["IND WATCHES/WARNINGS/ADVISORIES"]["detail"] is None
    assert result["IND WATCHES/WARNINGS/ADVISORIES"]["text"] == "None."



def parse_issued_at_success(iem_source):

    text = load_text("afdind_standard.txt")

    result = iem_source._parse_(text)

    pass


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (".DISCUSSION (This evening through Thursday)...", "DISCUSSION"),
        (".AVIATION /18Z TAFS THROUGH 18Z FRIDAY/...", "AVIATION"),
        (".KEY MESSAGES...", "KEY MESSAGES"),
        (".IND WATCHES/WARNINGS/ADVISORIES...", "IND WATCHES/WARNINGS/ADVISORIES"),
        (".SHORT TERM /Tonight Through Friday/...", "SHORT TERM"),
    ],
)
def test_parse_section_name(iem_source, line, expected):
    assert iem_source._parse_section_name(line) == expected
    
def parse_issued_at_failure():
    pass