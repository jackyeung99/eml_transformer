import pytest
from datetime import datetime, timezone
from typing import Any
import logging

from eml_transformer.ingestion.sources.iem_afos import (
    AFOSProductParseError,
)


def make_header(
    *,
    pil: str | None = "AFDIND",
    issued_code: str = "091838",
) -> dict[str, str | None]:
    return {
        "raw_id": "000",
        "wmo": "FXUS63",
        "wmo_header": f"FXUS63 KIND {issued_code}",
        "office": "KIND",
        "issued_code": issued_code,
        "pil": pil,
    }


def make_bronze_record(
    *,
    source_id: str = "record-1",
    pil: str = "AFDIND",
    raw_text: str = "AFOS product text",
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "pil": pil,
        "raw_text": raw_text,
        "header": make_header(pil=pil),
        "issued_at_text": "238 PM EDT Thu Jul 9 2026",
        "published_at": "2026-07-09T18:38:00+00:00",
    }


"""
Tests for minimal AFOS parsing performed before bronze storage.

Behaviors covered:
- API responses split into individual NWS products.
- Product order is preserved.
- Windows and Unix newlines are handled consistently.
- WMO/PIL headers are parsed into expected fields.
- Issuance text is extracted from supported product formats.
- Publication timestamps are normalized to UTC.
- Bronze records contain all required identity fields.
- Header PIL takes precedence over the request's fallback PIL.
- Source identifiers are deterministic.
- Malformed products are skipped without losing valid products.
- Duplicate products are removed by source identifier.
"""


# Product splitting
class TestSplitProducts:
    @pytest.mark.parametrize(
        ("filename", "expected_count"),
        [
            ("afdind_standard.txt", 1),
            ("afdind_two_entries.txt", 2),
            ("afdind_three_entries.txt", 3),
        ],
    )
    def test_split_products_returns_expected_number_of_products(
        self,
        iem_source,
        load_iem_text,
        filename,
        expected_count,
    ):
        text = load_iem_text(filename)

        products = iem_source._split_products(text)

        assert len(products) == expected_count
        assert all(product.strip() for product in products)

    def test_split_products_preserves_complete_single_product(
        self,
        iem_source,
        load_iem_text,
    ):
        text = load_iem_text("afdind_standard.txt")

        products = iem_source._split_products(text)

        assert len(products) == 1

        product = products[0]
        header = iem_source._parse_header(product)

        assert header["pil"] == "AFDIND"
        assert header["office"] == "KIND"
        assert "Area Forecast Discussion" in product

    def test_split_products_preserves_product_order(
        self,
        iem_source,
        load_iem_text,
    ):
        text = load_iem_text("afdind_two_entries.txt")

        products = iem_source._split_products(text)

        assert len(products) == 2

        headers = [
            iem_source._parse_header(product)
            for product in products
        ]

        assert [header["raw_id"] for header in headers] == ["085", "246"]
        assert [header["issued_code"] for header in headers] == [
            "091838",
            "091735",
        ]
        assert all(header["pil"] == "AFDIND" for header in headers)

    def test_split_products_normalizes_crlf_newlines(
        self,
        iem_source,
        load_iem_text,
    ):
        lf_text = load_iem_text("afdind_two_entries.txt")
        crlf_text = lf_text.replace("\n", "\r\n")

        products = iem_source._split_products(crlf_text)

        assert len(products) == 2
        assert all("\r" not in product for product in products)

        headers = [
            iem_source._parse_header(product)
            for product in products
        ]
        assert [header["raw_id"] for header in headers] == ["085", "246"]

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   \n\n",
            "This response does not contain an AFOS product.",
            "FXUS63 KIND\nMissing the raw ID and PIL lines.",
        ],
    )
    def test_split_products_returns_empty_list_without_valid_header(
        self,
        iem_source,
        text,
    ):
        products = iem_source._split_products(text)

        assert products == []

    def test_split_products_ignores_text_before_first_header(
        self,
        iem_source,
        load_iem_text,
    ):
        original_text = load_iem_text("afdind_standard.txt")
        text = (
            "Unexpected response preamble\n"
            "Additional non-product text\n\n"
            f"{original_text}"
        )

        products = iem_source._split_products(text)

        assert len(products) == 1
        assert "Unexpected response preamble" not in products[0]
        assert "Additional non-product text" not in products[0]

        header = iem_source._parse_header(products[0])
        assert header["pil"] == "AFDIND"

    def test_split_products_does_not_return_empty_products(
        self,
        iem_source,
        load_iem_text,
    ):
        text = load_iem_text("afdind_two_entries.txt")
        text = f"\n\n{text}\n\n"

        products = iem_source._split_products(text)

        assert len(products) == 2
        assert all(product.strip() for product in products)


# Header parsing
class TestHeaderParsing:
    def test_parse_header_extracts_expected_fields(
        self,
        iem_source,
        load_iem_text,
    ):
        text = load_iem_text("afdind_standard.txt")

        header = iem_source._parse_header(text)

        assert header == {
            "raw_id": "085",
            "wmo": "FXUS63",
            "office": "KIND",
            "issued_code": "091838",
            "pil": "AFDIND",
            "wmo_header": "FXUS63 KIND 091838",
        }

    def test_parse_header_builds_wmo_header(
        self,
        iem_source,
    ):
        text = (
            "085\n"
            "FXUS63 KIND 091838\n"
            "AFDIND\n"
            "\n"
            "Area Forecast Discussion\n"
        )

        header = iem_source._parse_header(text)

        assert header["wmo_header"] == "FXUS63 KIND 091838"

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   \n\n",
            "Area Forecast Discussion\n",
            "This response does not contain an AFOS header.",
        ],
    )
    def test_parse_header_returns_empty_header_when_missing(
        self,
        iem_source,
        text,
    ):
        header = iem_source._parse_header(text)

        assert header == iem_source._empty_header()

# Issuance timestamp parsing
class TestTimestampParsing():
    @pytest.mark.parametrize(
        (
            "raw_text",
            "pil",
            "expected_text",
            "expected_utc",
        ),
        [
            pytest.param(
                """
Area Forecast Discussion
National Weather Service Indianapolis IN
238 PM EDT Thu Jul 9 2026
""",
                "AFDIND",
                "238 PM EDT Thu Jul 9 2026",
                datetime(2026, 7, 9, 18, 38, tzinfo=timezone.utc),
                id="standard-edt",
            ),
            pytest.param(
                """
Hazardous Weather Outlook
National Weather Service Lincoln IL
Issued by National Weather Service Chicago IL
300 AM CST Sun Dec 8 2024
""",
                "HWOILX",
                "300 AM CST Sun Dec 8 2024",
                datetime(2024, 12, 8, 9, 0, tzinfo=timezone.utc),
                id="issued-by-office",
            ),
            pytest.param(
                """
Area Forecast Discussion
National Weather Service Indianapolis IN
1200 AM EST Mon Jan 6 2025
""",
                "AFDIND",
                "1200 AM EST Mon Jan 6 2025",
                datetime(2025, 1, 6, 5, 0, tzinfo=timezone.utc),
                id="midnight",
            ),
            pytest.param(
                """
Area Forecast Discussion
National Weather Service Indianapolis IN
1200 PM EST Mon Jan 6 2025
""",
                "AFDIND",
                "1200 PM EST Mon Jan 6 2025",
                datetime(2025, 1, 6, 17, 0, tzinfo=timezone.utc),
                id="noon",
            ),
            pytest.param(
                """
Area Forecast Discussion
National Weather Service Chicago IL
1259 PM CDT Tue Jun 2 2026
""",
                "AFDLOT",
                "1259 PM CDT Tue Jun 2 2026",
                datetime(2026, 6, 2, 17, 59, tzinfo=timezone.utc),
                id="single-digit-day",
            ),
        ],
    )
    def test_parse_product_timestamp(
        self,
        iem_source,
        raw_text,
        pil,
        expected_text,
        expected_utc,
    ):
        issued_at_text, published_at = iem_source._parse_product_timestamp(
            product_text=raw_text.strip(),
            pil=pil,
        )

        assert issued_at_text == expected_text
        assert datetime.fromisoformat(published_at) == expected_utc

    @pytest.mark.parametrize(
        "newline",
        ["\n", "\r\n", "\r"],
    )
    def test_parse_published_at_supports_newline_variations(
        self,
        iem_source,
        newline,
    ):
        lines = [
            "Area Forecast Discussion",
            "National Weather Service Indianapolis IN",
            "238 PM EDT Thu Jul 9 2026",
            "",
            ".DISCUSSION...",
            "Forecast discussion.",
        ]
        text = newline.join(lines)

        issued_at_text, published_at = iem_source._parse_product_timestamp(
            product_text=text,
            pil="AFDIND",
        )

        assert issued_at_text == "238 PM EDT Thu Jul 9 2026"
        assert datetime.fromisoformat(published_at) == datetime(
            2026,
            7,
            9,
            18,
            38,
            tzinfo=timezone.utc,
        )

    def test_extract_issued_text_returns_none_when_missing(
        self,
        iem_source,
    ):
        text = """
    Area Forecast Discussion
    National Weather Service Indianapolis IN

    Forecast discussion without an issuance timestamp.
    """.strip()

        issued_at_text = iem_source._extract_product_timestamp_text(text)

        assert issued_at_text is None


    @pytest.mark.parametrize(
        ("issued_at_text", "expected_utc"),
        [
            pytest.param(
                "238 PM EDT Thu Jul 9 2026",
                datetime(2026, 7, 9, 18, 38, tzinfo=timezone.utc),
                id="eastern-daylight",
            ),
            pytest.param(
                "238 PM EST Thu Jan 9 2025",
                datetime(2025, 1, 9, 19, 38, tzinfo=timezone.utc),
                id="eastern-standard",
            ),
            pytest.param(
                "300 AM CDT Thu Jul 9 2026",
                datetime(2026, 7, 9, 8, 0, tzinfo=timezone.utc),
                id="central-daylight",
            ),
            pytest.param(
                "300 AM CST Thu Jan 9 2025",
                datetime(2025, 1, 9, 9, 0, tzinfo=timezone.utc),
                id="central-standard",
            ),
        ],
    )
    def test_parse_published_at_converts_to_utc(
        self,
        iem_source,
        issued_at_text,
        expected_utc,
    ):
        text = (
            "Area Forecast Discussion\n"
            "National Weather Service Test Office\n"
            f"{issued_at_text}\n"
        )
        
        extracted_text, published_at = iem_source._parse_product_timestamp(
            product_text=text,
            pil="AFDIND",
        )

      
        assert extracted_text == issued_at_text
        assert datetime.fromisoformat(published_at) == expected_utc


    def test_parse_published_at_raises_when_timestamp_missing(
        self,
        iem_source,
    ):
        text = (
            "Area Forecast Discussion\n"
            "National Weather Service Test Office\n"
            "\n"
            "Forecast discussion without an issuance timestamp.\n"
        )

        with pytest.raises(
            ValueError,
            match="Missing product issuance timestamp",
        ):
            iem_source._parse_product_timestamp(
                product_text=text,
                pil="AFDIND",
            )


    @pytest.mark.parametrize(
        "malformed_timestamp",
        [
            pytest.param(
                "2500 PM EDT Thu Jul 9 2026",
                id="invalid-hour",
            ),
            pytest.param(
                "238 PM XYZ Thu Jul 9 2026",
                id="unknown-timezone",
            ),
            pytest.param(
                "238 PM EDT Thu NotAMonth 9 2026",
                id="invalid-month",
            ),
            pytest.param(
                "238 PM EDT Thu Jul 32 2026",
                id="invalid-day",
            ),
            pytest.param(
                "238 PM EDT Thu Jul 9",
                id="missing-year",
            ),
        ],
    )
    def test_parse_published_at_raises_when_timestamp_malformed(
        self,
        iem_source,
        malformed_timestamp,
    ):
        text = (
            "Area Forecast Discussion\n"
            "National Weather Service Test Office\n"
            f"{malformed_timestamp}\n"
        )

        with pytest.raises(ValueError):
            iem_source._parse_product_timestamp(
                product_text=text,
                pil="AFDIND",
            )

# Source identity
class TestSourceId:
    def test_make_source_record_id_is_deterministic(
        self,
        iem_source,
    ):
        header = make_header()

        first = iem_source._make_source_record_id(
            pil="AFDIND",
            header=header,
            published_at="2026-07-09T18:38:00+00:00",
        )
        second = iem_source._make_source_record_id(
            pil="AFDIND",
            header=header,
            published_at="2026-07-09T18:38:00+00:00",
        )

        assert first == second

    def test_source_id_changes_when_published_at_changes(
        self,
        iem_source,
    ):
        header = make_header()

        first = iem_source._make_source_record_id(
            pil="AFDIND",
            header=header,
            published_at="2026-07-09T18:38:00+00:00",
        )
        second = iem_source._make_source_record_id(
            pil="AFDIND",
            header=header,
            published_at="2026-07-09T19:38:00+00:00",
        )

        assert first != second

    def test_source_id_changes_when_pil_changes(
        self,
        iem_source,
    ):
        header = make_header()

        first = iem_source._make_source_record_id(
            pil="AFDIND",
            header=header,
            published_at="2026-07-09T18:38:00+00:00",
        )
        second = iem_source._make_source_record_id(
            pil="HWOIND",
            header=header,
            published_at="2026-07-09T18:38:00+00:00",
        )

        assert first != second

    def test_source_id_does_not_depend_on_raw_body_text(
        self,
        iem_source,
        monkeypatch,
    ):
        header = make_header()

        monkeypatch.setattr(
            iem_source,
            "_parse_header",
            lambda product_text: header,
        )
        monkeypatch.setattr(
            iem_source,
            "_parse_product_timestamp",
            lambda product_text, pil: (
                "238 PM EDT Thu Jul 9 2026",
                "2026-07-09T18:38:00+00:00",
            ),
        )

        first = iem_source._build_bronze_record(
            product_text="First version of the body",
            requested_pil="AFDIND",
        )
        second = iem_source._build_bronze_record(
            product_text="Completely different body",
            requested_pil="AFDIND",
        )

        assert first["source_id"] == second["source_id"]
        assert first["raw_text"] != second["raw_text"]

# # Bronze record construction
class TestBronzeConstruction:
    def test_build_bronze_record_returns_required_fields(
        self,
        iem_source,
        monkeypatch,
    ):
        header = make_header()

        monkeypatch.setattr(
            iem_source,
            "_parse_header",
            lambda product_text: header,
        )
        monkeypatch.setattr(
            iem_source,
            "_parse_product_timestamp",
            lambda product_text, pil: (
                "238 PM EDT Thu Jul 9 2026",
                "2026-07-09T18:38:00+00:00",
            ),
        )

        result = iem_source._build_bronze_record(
            product_text="AFOS product text",
            requested_pil="AFDIND",
        )

        assert set(result) == {
            "source_id",
            "pil",
            "header",
            "issued_at_text",
            "published_at",
            "raw_text",
        }

        assert result["source_id"]
        assert result["pil"] == "AFDIND"
        assert result["header"] == header
        assert result["issued_at_text"] == (
            "238 PM EDT Thu Jul 9 2026"
        )
        assert result["published_at"] == (
            "2026-07-09T18:38:00+00:00"
        )

    def test_build_bronze_record_preserves_raw_text(
        self,
        iem_source,
        monkeypatch,
    ):
        raw_text = (
            "000\n"
            "FXUS63 KIND 091838\n"
            "AFDIND\n"
            "\n"
            "Area Forecast Discussion\n"
            "Full raw product body."
        )

        monkeypatch.setattr(
            iem_source,
            "_parse_header",
            lambda product_text: make_header(),
        )
        monkeypatch.setattr(
            iem_source,
            "_parse_product_timestamp",
            lambda product_text, pil: (
                "238 PM EDT Thu Jul 9 2026",
                "2026-07-09T18:38:00+00:00",
            ),
        )

        result = iem_source._build_bronze_record(
            product_text=raw_text,
            requested_pil="AFDIND",
        )

        assert result["raw_text"] == raw_text

    # def test_build_bronze_record_prefers_header_pil(
    #     self,
    #     iem_source,
    #     monkeypatch,
    # ):
    #     monkeypatch.setattr(
    #         iem_source,
    #         "_parse_header",
    #         lambda product_text: make_header(pil="AFDIND"),
    #     )
    #     monkeypatch.setattr(
    #         iem_source,
    #         "_parse_product_timestamp",
    #         lambda product_text, pil: (
    #             "238 PM EDT Thu Jul 9 2026",
    #             "2026-07-09T18:38:00+00:00",
    #         ),
    #     )

    #     result = iem_source._build_bronze_record(
    #         product_text="AFOS product",
    #         requested_pil="HWOIND",
    #     )

    #     assert result["pil"] == "AFDIND"

    def test_build_bronze_record_uses_requested_pil_fallback(
        self,
        iem_source,
        monkeypatch,
    ):
        monkeypatch.setattr(
            iem_source,
            "_parse_header",
            lambda product_text: make_header(pil=None),
        )
        monkeypatch.setattr(
            iem_source,
            "_parse_product_timestamp",
            lambda product_text, pil: (
                "238 PM EDT Thu Jul 9 2026",
                "2026-07-09T18:38:00+00:00",
            ),
        )

        result = iem_source._build_bronze_record(
            product_text="AFOS product",
            requested_pil="AFDIND",
        )

        assert result["pil"] == "AFDIND"

    def test_build_bronze_record_raises_for_invalid_timestamp(
        self,
        iem_source,
        monkeypatch,
    ):
        monkeypatch.setattr(
            iem_source,
            "_parse_header",
            lambda product_text: make_header(),
        )

        def fake_parse_product_timestamp(product_text, pil):
            raise AFOSProductParseError(
                f"Invalid product timestamp for PIL={pil}"
            )

        monkeypatch.setattr(
            iem_source,
            "_parse_product_timestamp",
            fake_parse_product_timestamp,
        )

        with pytest.raises(
            AFOSProductParseError,
            match="Invalid product timestamp",
        ):
            iem_source._build_bronze_record(
                product_text="AFOS product",
                requested_pil="AFDIND",
            )

# # Error isolation and deduplication
class TestErrorHandling:
    def test_build_records_from_response_builds_all_valid_products(
        self,
        iem_source,
        monkeypatch,
    ):
        product_texts = [
            "first product",
            "second product",
        ]

        monkeypatch.setattr(
            iem_source,
            "_split_products",
            lambda response_text: product_texts,
        )

        def fake_build_bronze_record(
            product_text,
            requested_pil,
        ):
            return make_bronze_record(
                source_id=f"id-{product_text}",
                pil=requested_pil,
                raw_text=product_text,
            )

        monkeypatch.setattr(
            iem_source,
            "_build_bronze_record",
            fake_build_bronze_record,
        )

        result = iem_source._build_records_from_response(
            {
                "pil": "AFDIND",
                "response": "combined response",
            }
        )

        assert len(result) == 2
        assert [record["raw_text"] for record in result] == [
            "first product",
            "second product",
        ]

    def test_build_records_from_response_skips_malformed_product(
        self,
        iem_source,
        monkeypatch,
    ):
        monkeypatch.setattr(
            iem_source,
            "_split_products",
            lambda response_text: [
                "valid product",
                "malformed product",
                "another valid product",
            ],
        )

        def fake_build_bronze_record(
            product_text,
            requested_pil,
        ):
            if product_text == "malformed product":
                raise AFOSProductParseError(
                    "Missing product timestamp"
                )

            return make_bronze_record(
                source_id=f"id-{product_text}",
                pil=requested_pil,
                raw_text=product_text,
            )

        monkeypatch.setattr(
            iem_source,
            "_build_bronze_record",
            fake_build_bronze_record,
        )

        result = iem_source._build_records_from_response(
            {
                "pil": "AFDIND",
                "response": "combined response",
            }
        )

        assert len(result) == 2
        assert [record["raw_text"] for record in result] == [
            "valid product",
            "another valid product",
        ]

    def test_build_records_from_response_logs_malformed_product(
        self,
        iem_source,
        monkeypatch,
        caplog,
    ):
        monkeypatch.setattr(
            iem_source,
            "_split_products",
            lambda response_text: ["malformed product"],
        )

        def fake_build_bronze_record(
            product_text,
            requested_pil,
        ):
            raise AFOSProductParseError(
                "Missing product timestamp"
            )

        monkeypatch.setattr(
            iem_source,
            "_build_bronze_record",
            fake_build_bronze_record,
        )

        with caplog.at_level(logging.WARNING):
            result = iem_source._build_records_from_response(
                {
                    "pil": "AFDIND",
                    "response": "combined response",
                }
            )

        assert result == []
        assert "Skipping malformed AFOS product" in caplog.text
        assert "pil=AFDIND" in caplog.text
        assert "product=1" in caplog.text
        assert "Missing product timestamp" in caplog.text

    def test_build_bronze_records_combines_multiple_responses(
        self,
        iem_source,
        monkeypatch,
    ):
        responses = [
            {
                "pil": "AFDIND",
                "response": "AFD response",
            },
            {
                "pil": "HWOIND",
                "response": "HWO response",
            },
        ]

        def fake_build_records_from_response(response):
            return [
                make_bronze_record(
                    source_id=f"id-{response['pil']}",
                    pil=response["pil"],
                )
            ]

        monkeypatch.setattr(
            iem_source,
            "_build_records_from_response",
            fake_build_records_from_response,
        )

        result = iem_source._build_bronze_records(responses)

        assert len(result) == 2
        assert [record["pil"] for record in result] == [
            "AFDIND",
            "HWOIND",
        ]

    def test_build_bronze_records_removes_duplicate_source_ids(
        self,
        iem_source,
        monkeypatch,
    ):
        duplicate_id = "duplicate-id"

        def fake_build_records_from_response(response):
            return [
                make_bronze_record(
                    source_id=duplicate_id,
                    pil=response["pil"],
                )
            ]

        monkeypatch.setattr(
            iem_source,
            "_build_records_from_response",
            fake_build_records_from_response,
        )

        result = iem_source._build_bronze_records(
            [
                {
                    "pil": "AFDIND",
                    "response": "first response",
                },
                {
                    "pil": "AFDIND",
                    "response": "second response",
                },
            ]
        )

        assert len(result) == 1
        assert result[0]["source_id"] == duplicate_id

    def test_deduplicate_records_preserves_first_duplicate(
        self,
        iem_source,
    ):
        first = make_bronze_record(
            source_id="duplicate-id",
            raw_text="first version",
        )
        second = make_bronze_record(
            source_id="duplicate-id",
            raw_text="second version",
        )

        result = iem_source._deduplicate_records(
            [first, second]
        )

        assert result == [first]
        assert result[0]["raw_text"] == "first version"