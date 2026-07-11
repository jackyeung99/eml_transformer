from __future__ import annotations

import logging
import random
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from eml_transformer.ingestion.base import TextSource
from eml_transformer.ingestion.registry import register_source
from eml_transformer.ingestion.schema import TextRecord
from eml_transformer.utils.dates import parse_issued_at
from eml_transformer.utils.stamping import stable_hash

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedSection:
    """One logical section extracted from an AFOS product."""

    name: str
    detail: str | None
    text: str
    issued_at_text: str | None = None
    published_at: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


@register_source("iem_afos")
class IEMAFOSSource(TextSource):
    """Ingest archived NWS products from the IEM AFOS archive.

    Ingestion performs only the parsing needed to split, identify, and
    checkpoint products before they are written to bronze. Standardization
    performs section parsing and constructs the common ``TextRecord`` used in
    silver.
    """

    name = "iem_afos"
    source_type = "api"
    update_mode = "incremental"
    supports_backfill = True
    default_lookback_days = 3

    BASE_URL = (
        "https://mesonet.agron.iastate.edu/"
        "cgi-bin/afos/retrieve.py"
    )

    DEFAULT_MISO_WFOS = [
        "IND",  # Indianapolis
        "IWX",  # Northern Indiana
        "LOT",  # Chicago
        "ILX",  # Central Illinois
        "LSX",  # St. Louis
        "DVN",  # Quad Cities
        "DMX",  # Des Moines
        "ARX",  # La Crosse
        "MKX",  # Milwaukee
        "GRR",  # Grand Rapids
        "DTX",  # Detroit
        "APX",  # Gaylord
        "MPX",  # Twin Cities
        "DLH",  # Duluth
        "PAH",  # Paducah
        "LMK",  # Louisville
        "MEG",  # Memphis
        "LZK",  # Little Rock
        "JAN",  # Jackson, Mississippi
        "LIX",  # New Orleans / Baton Rouge
        "MOB",  # Mobile
        "BMX",  # Birmingham
    ]

    DEFAULT_PRODUCT_TYPES = [
        "AFD",  # Area Forecast Discussion
        "HWO",  # Hazardous Weather Outlook
        "NPW",  # Non-precipitation warnings
        "WSW",  # Winter storm watches and warnings
        "LSR",  # Local Storm Reports
        "SPS",  # Special Weather Statements
    ]

    PREFERRED_TEXT_SECTIONS = ("KEY MESSAGES", "SHORT TERM")

    HEADER_RE = re.compile(
        r"""
        (?P<seq>\d{3})\s+
        (?P<wmo>[A-Z]{4}\d{2})\s+
        (?P<office>[A-Z]{4})\s+
        (?P<ddhhmm>\d{6})\s+
        (?P<pil>[A-Z]{6})
        """,
        re.VERBOSE,
    )

    SECTION_RE = re.compile(
        r"(?ms)^"
        r"\.(?P<section>[A-Z0-9 /-]+?)"
        r"(?:\s*\((?P<section_detail>.*?)\))?"
        r"\.\.\."
        r"(?P<content>.*?)"
        r"(?=\n&&|\n\.[A-Z0-9 /-]+(?:\s*\(.*?\))?\.\.\.|\n\$\$|\Z)"
    )

    ISSUED_AT_RE = re.compile(r"(?m)^Issued at .+$")
    NWS_TIMESTAMP_RE = re.compile(r"(?m)^National Weather Service .*\n(.+)$")

    def __init__(
        self,
        pil: str | None = None,
        wfos: list[str] | None = None,
        product_types: list[str] | None = None,
        limit: int = 9999,
        fmt: str = "text",
        timeout: int = 30,
        session: requests.Session | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        request_delay: tuple[float, float] = (0.5, 1.5),
    ) -> None:
        self.pil = pil.upper() if pil else None
        self.wfos = self._normalize_codes(wfos or self.DEFAULT_MISO_WFOS)
        self.product_types = self._normalize_codes(
            product_types or self.DEFAULT_PRODUCT_TYPES
        )
        self.limit = limit
        self.fmt = fmt
        self.timeout = timeout
        self.base_url = self.BASE_URL

        # These dependencies are injectable so API tests require no real
        # requests or waiting.
        self._session = session or requests.Session()
        self._sleep = sleep_fn
        self._request_delay = request_delay

    # ------------------------------------------------------------------
    # Public pipeline interface
    # ------------------------------------------------------------------

    def fetch_records(
        self,
        from_date: str,
        to_date: str,
    ) -> list[dict[str, Any]]:
        """Fetch and minimally parse source-native records for bronze."""
        responses = self._fetch_raw(from_date=from_date, to_date=to_date)
        return self._parse_records(responses)

    def standardize_record(self, record: dict[str, Any]) -> TextRecord:
        """Convert one bronze AFOS record into the silver schema."""
        self._validate_bronze_record(record)

        pil = str(record["pil"])
        raw_text = str(record["raw_text"])
        header = record.get("header") or self._parse_header(raw_text)
        sections = self._parse_sections(raw_text)

        issued_at_text = record.get("issued_at_text")
        published_at = record.get("published_at")
        if not published_at:
            issued_at_text, published_at = self._parse_published_at(
                raw_text=raw_text,
                pil=pil,
            )

        product_type = pil[:3]
        office = self._resolve_office(pil=pil, header=header)

        return TextRecord(
            record_id=str(record["source_id"]),
            source=self.name,
            source_type=self.source_type,
            title=self._make_title(
                product_type=product_type,
                office=office,
                issued_at_text=issued_at_text,
            ),
            text=self._build_text(sections=sections, raw_text=raw_text),
            published_at=str(published_at),
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            url=self.base_url,
            region=office[-3:],
            categories=[
                "weather",
                "nws",
                "iem",
                "afos",
                product_type.lower(),
            ],
            metadata={
                "pil": pil,
                "product_type": product_type,
                "office": office,
                "header": header,
                "sections": {
                    name: section.to_dict()
                    for name, section in sections.items()
                },
                "issued_at_text": issued_at_text,
                "published_at_standardized": published_at,
            },
            raw=raw_text,
        )

    def get_checkpoint_value(
        self,
        record: dict[str, Any],
    ) -> datetime | None:
        """Return the record timestamp used by incremental ingestion."""
        published_at = record.get("published_at")
        if not published_at:
            return None

        return self._parse_iso_datetime(
            str(published_at),
            field_name="checkpoint",
        )

    # ------------------------------------------------------------------
    # API access
    # ------------------------------------------------------------------

    def _fetch_raw(
        self,
        from_date: str,
        to_date: str,
    ) -> list[dict[str, str]]:
        responses: list[dict[str, str]] = []

        for pil in self._pils_to_fetch():
            text = self._fetch_pil(
                pil=pil,
                from_date=from_date,
                to_date=to_date,
            )
            if text is not None:
                responses.append({"pil": pil, "response": text})

        return responses

    def _fetch_pil(
        self,
        pil: str,
        from_date: str,
        to_date: str,
    ) -> str | None:
        minimum_delay, maximum_delay = self._request_delay
        self._sleep(random.uniform(minimum_delay, maximum_delay))

        response = self._session.get(
            self.base_url,
            params={
                "pil": pil,
                "sdate": from_date,
                "edate": to_date,
                "limit": self.limit,
                "fmt": self.fmt,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        text = response.text.strip()
        if not text or text.startswith("ERROR:"):
            return None

        return text

    def _pils_to_fetch(self) -> list[str]:
        if self.pil:
            return [self.pil]

        return [
            f"{product_type}{wfo}"
            for product_type in self.product_types
            for wfo in self.wfos
        ]

    # ------------------------------------------------------------------
    # Bronze parsing
    # ------------------------------------------------------------------

    def _parse_records(
        self,
        raw_responses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for response_item in raw_responses:
            for record in self._parse_response_item(response_item):
                source_id = record["source_id"]
                if source_id in seen_ids:
                    continue

                seen_ids.add(source_id)
                records.append(record)

        return records

    def _parse_response_item(
        self,
        item: dict[str, Any],
    ) -> list[dict[str, Any]]:
        fallback_pil = str(item["pil"])
        response_text = str(item["response"])
        records: list[dict[str, Any]] = []

        for chunk_number, chunk in enumerate(
            self._split_products(response_text),
            start=1,
        ):
            try:
                records.append(
                    self._parse_product_chunk(
                        chunk=chunk,
                        fallback_pil=fallback_pil,
                    )
                )
            except (TypeError, ValueError):
                logger.warning(
                    "Skipping malformed AFOS product | pil=%s | chunk=%d",
                    fallback_pil,
                    chunk_number,
                    exc_info=True,
                )

        return records

    def _parse_product_chunk(
        self,
        chunk: str,
        fallback_pil: str,
    ) -> dict[str, Any]:
        header = self._parse_header(chunk)
        parsed_pil = header.get("pil") or fallback_pil

        issued_at_text, published_at = self._parse_published_at(
            raw_text=chunk,
            pil=parsed_pil,
        )
        source_id = self._make_source_record_id(
            pil=parsed_pil,
            header=header,
            published_at=published_at,
        )

        return {
            "source_id": source_id,
            "pil": parsed_pil,
            "raw_text": chunk,
            "header": header,
            "issued_at_text": issued_at_text,
            "published_at": published_at,
        }

    def _split_products(self, raw: str) -> list[str]:
        text = self._normalize_newlines(raw)
        header_matches = list(self.HEADER_RE.finditer(text))

        products: list[str] = []
        for index, match in enumerate(header_matches):
            next_index = index + 1
            end = (
                header_matches[next_index].start()
                if next_index < len(header_matches)
                else len(text)
            )
            products.append(text[match.start():end].strip())

        return products

    def _parse_header(self, text: str) -> dict[str, str | None]:
        match = self.HEADER_RE.search(text)
        if match is None:
            return self._empty_header()

        wmo = match.group("wmo")
        office = match.group("office")
        issued_code = match.group("ddhhmm")

        return {
            "raw_id": match.group("seq"),
            "wmo": wmo,
            "wmo_header": f"{wmo} {office} {issued_code}",
            "office": office,
            "issued_code": issued_code,
            "pil": match.group("pil"),
        }

    def _parse_published_at(
        self,
        raw_text: str,
        pil: str,
    ) -> tuple[str, str]:
        issued_at_text = self._extract_issued_text(raw_text)
        if not issued_at_text:
            raise ValueError(f"Missing issuance timestamp for PIL={pil}")

        try:
            published_at = parse_issued_at(issued_at_text)
        except Exception as exc:
            raise ValueError(
                f"Failed to parse published_at for PIL={pil}: "
                f"{issued_at_text!r}"
            ) from exc

        if not isinstance(published_at, str) or not published_at:
            raise ValueError(
                f"Missing published_at for PIL={pil}: {issued_at_text!r}"
            )

        published_at_utc = self._parse_iso_datetime(
            published_at,
            field_name=f"published_at for PIL={pil}",
        )
        return issued_at_text, published_at_utc.isoformat()

    def _make_source_record_id(
        self,
        pil: str,
        header: dict[str, str | None],
        published_at: str,
    ) -> str:
        return stable_hash(
            {
                "source": self.name,
                "pil": pil,
                "office": header.get("office"),
                "issued_code": header.get("issued_code"),
                "raw_id": header.get("raw_id"),
                "published_at": published_at,
            }
        )

    # ------------------------------------------------------------------
    # Silver parsing
    # ------------------------------------------------------------------

    def _parse_sections(self, text: str) -> dict[str, ParsedSection]:
        sections: dict[str, ParsedSection] = {}

        for match in self.SECTION_RE.finditer(self._normalize_newlines(text)):
            name = self._normalize_section_name(match.group("section"))
            detail = self._clean_optional_text(match.group("section_detail"))
            content, issued_at_text = self._clean_section_text(
                match.group("content")
            )

            sections[name] = ParsedSection(
                name=name,
                detail=detail,
                text=content,
                issued_at_text=issued_at_text,
                published_at=self._try_parse_issued_at(issued_at_text),
            )

        return sections

    def _clean_section_text(
        self,
        content: str,
    ) -> tuple[str, str | None]:
        issued_at_text = self._extract_issued_text(content)
        cleaned = self.ISSUED_AT_RE.sub("", content)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned, issued_at_text

    def _build_text(
        self,
        sections: dict[str, ParsedSection],
        raw_text: str,
    ) -> str:
        preferred_text = [
            sections[name].text
            for name in self.PREFERRED_TEXT_SECTIONS
            if name in sections and sections[name].text
        ]

        if preferred_text:
            return "\n\n".join(preferred_text)

        return raw_text.strip()

    def _extract_issued_text(self, text: str) -> str | None:
        match = self.ISSUED_AT_RE.search(text)
        if match:
            return match.group(0).strip()

        match = self.NWS_TIMESTAMP_RE.search(text)
        if match:
            return match.group(1).strip()

        return None

    def _resolve_office(
        self,
        pil: str,
        header: dict[str, str | None],
    ) -> str:
        office = header.get("office")
        if office:
            return office

        if len(pil) >= 6:
            return pil[3:]

        raise ValueError(f"Could not determine office for PIL={pil}")

    def _make_title(
        self,
        product_type: str,
        office: str | None,
        issued_at_text: str | None,
    ) -> str:
        return " | ".join(
            part
            for part in (product_type, office, issued_at_text)
            if part
        )

    # ------------------------------------------------------------------
    # Shared validation and normalization helpers
    # ------------------------------------------------------------------

    def _validate_bronze_record(self, record: dict[str, Any]) -> None:
        required_fields = {"source_id", "pil", "raw_text"}
        missing_fields = [
            field
            for field in sorted(required_fields)
            if not record.get(field)
        ]

        if missing_fields:
            raise ValueError(
                "AFOS bronze record is missing required fields: "
                f"{missing_fields}"
            )

    def _try_parse_issued_at(self, value: str | None) -> str | None:
        if not value:
            return None

        try:
            parsed = parse_issued_at(value)
            if not isinstance(parsed, str) or not parsed:
                return None

            return self._parse_iso_datetime(
                parsed,
                field_name="section published_at",
            ).isoformat()
        except (TypeError, ValueError):
            logger.debug(
                "Could not parse AFOS section timestamp | value=%r",
                value,
                exc_info=True,
            )
            return None

    @staticmethod
    def _parse_iso_datetime(value: str, field_name: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"Malformed ISO datetime for {field_name}: {value!r}"
            ) from exc

        if parsed.tzinfo is None:
            raise ValueError(
                f"Timezone-naive datetime for {field_name}: {value!r}"
            )

        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _normalize_codes(values: list[str]) -> list[str]:
        return [value.strip().upper() for value in values]

    @staticmethod
    def _normalize_newlines(value: str) -> str:
        return value.replace("\r\n", "\n").replace("\r", "\n").strip()

    @staticmethod
    def _normalize_section_name(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().upper()

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None

        cleaned = re.sub(r"\s+", " ", value).strip()
        return cleaned or None

    @staticmethod
    def _empty_header() -> dict[str, str | None]:
        return {
            "raw_id": None,
            "wmo": None,
            "wmo_header": None,
            "office": None,
            "issued_code": None,
            "pil": None,
        }