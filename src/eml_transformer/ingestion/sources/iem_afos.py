from __future__ import annotations

import logging
import random
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from typing import Any

import requests

from eml_transformer.ingestion.base import TextSource
from eml_transformer.ingestion.registry import register_source
from eml_transformer.ingestion.schema import TextRecord, BronzeRecord
from eml_transformer.utils.stamping import stable_hash
from eml_transformer.utils.dates import utc_now

logger = logging.getLogger(__name__)

_AFOS_TZ_MAP = {
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
}

_AFOS_WEEKDAY_FIXES = {
    "Fr": "Fri",
    "Tu": "Tue",
    "Th": "Thu",
    "Sa": "Sat",
    "Su": "Sun",
    "Mo": "Mon",
    "We": "Wed",
}

class AFOSProductParseError(ValueError):
    """Raised when an AFOS product cannot become a bronze record."""


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

    NWS_TIMESTAMP_LINE = (
        r"(?:Issued at\s+)?"
        r"\d{1,4}\s+"
        r"(?:AM|PM)\s+"
        r"[A-Z]{2,5}\s+"
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        r"\d{1,2}\s+"
        r"\d{4}"
    )

    PRODUCT_TIMESTAMP_RE = re.compile(
        rf"""
        ^National[ ]Weather[ ]Service[^\n]*\n
        (?:Issued[ ]by[ ]National[ ]Weather[ ]Service[^\n]*\n)?
        (?P<issued_at>{NWS_TIMESTAMP_LINE})[ \t]*$
        """,
        re.MULTILINE | re.IGNORECASE | re.VERBOSE,
    )

    SECTION_TIMESTAMP_RE = re.compile(
        r"""
        ^(?P<issued_at>
            Issued[ ]at[ ]+
            \d{1,4}[ ]+
            (?:AM|PM)[ ]+
            [A-Z]{2,5}[ ]+
            (?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[ ]+
            (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[ ]+
            \d{1,2}[ ]+
            \d{4}
        )[ \t]*$
        """,
        re.MULTILINE | re.IGNORECASE | re.VERBOSE,
    )
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
        request_delay: tuple[float, float] = (0.25, 0.5),
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
        from_date: datetime,
        to_date: datetime,
    ) -> list[dict[str, Any]]:
        raw_responses = self._fetch_responses(
            from_date=from_date,
            to_date=to_date,
        )
        return self._build_bronze_records(raw_responses)


    def standardize_record(
        self,
        record: BronzeRecord,
    ) -> TextRecord:
        raw = record.raw

        pil = str(raw["pil"])
        product_text = str(raw["raw_text"])
        header = raw["header"]

        product_type = pil[:3]
        office = self._resolve_office(
            pil=pil,
            header=header,
        )
        sections = self._parse_sections(product_text)

        return TextRecord(
            record_id=record.record_id,
            source=record.source,
            source_type=self.source_type,
            title=self._build_title(
                product_type=product_type,
                office=office,
                issued_at_text=str(raw["issued_at_text"]),
            ),
            text=self._build_text(
                sections=sections,
                product_text=product_text,
            ),
            published_at=record.published_at,
            retrieved_at=record.retrieved_at,
            url=self.base_url,
            region=office[-3:],
            categories=self._build_categories(product_type),
            metadata=self._build_metadata(
                record=raw,
                product_type=product_type,
                office=office,
                sections=sections,
            ),
            raw=product_text,
        )


    # ------------------------------------------------------------------
    # API access
    # ------------------------------------------------------------------

    def _fetch_responses(
        self,
        from_date: datetime,
        to_date: datetime,
    ) -> list[dict[str, str]]:
        responses: list[dict[str, str]] = []

        for pil in self._pils_to_fetch():
            response_text = self._fetch_pil(
                pil=pil,
                from_date=from_date,
                to_date=to_date,
            )

            if response_text is not None:
                responses.append(
                    {
                        "pil": pil,
                        "response": response_text,
                    }
                )

        return responses


    def _fetch_pil(
        self,
        pil: str,
        from_date: datetime,
        to_date: datetime,
    ) -> str | None:
        self._wait_before_request()

        response = self._session.get(
            self.base_url,
            params=self._build_request_params(
                pil=pil,
                from_date=from_date,
                to_date=to_date,
            ),
            timeout=self.timeout,
        )
        response.raise_for_status()

        response_text = response.text.strip()

        if not response_text:
            return None

        if response_text.startswith("ERROR:"):
            return None

        return response_text
    
    def _build_request_params(
        self,
        pil: str,
        from_date: datetime,
        to_date: datetime,
    ) -> dict[str, str | int]:
        """Build query parameters for an IEM AFOS request."""
        return {
            "pil": pil,
            "sdate": from_date,
            "edate": to_date,
            "limit": self.limit,
            "fmt": self.fmt,
    }

    def _pils_to_fetch(self) -> list[str]:
        if self.pil:
            return [self.pil]

        return [
            f"{product_type}{wfo}"
            for product_type in self.product_types
            for wfo in self.wfos
        ]
    

    def _wait_before_request(self) -> None:
        """Apply the configured delay before an API request."""
        minimum_delay, maximum_delay = self._request_delay
        delay = random.uniform(minimum_delay, maximum_delay)
        self._sleep(delay)

    # ------------------------------------------------------------------
    # Bronze construction
    # ------------------------------------------------------------------

    def _build_bronze_records(
        self,
        responses: list[dict[str, str]],
    ) -> list[BronzeRecord]:
        records: list[BronzeRecord] = []

        for response in responses:
            records.extend(
                self._build_records_from_response(response)
            )

        return self._deduplicate_records(records)


    def _build_records_from_response(
        self,
        response: dict[str, str],
    ) -> list[BronzeRecord]:
        requested_pil = response["pil"]
        product_texts = self._split_products(response["response"])
        records: list[BronzeRecord] = []

        retrieved_at = utc_now()

        for product_number, product_text in enumerate(
            product_texts,
            start=1,
        ):
            try:
                record = self._build_bronze_record(
                    product_text=product_text,
                    requested_pil=requested_pil,
                    retrieved_at=retrieved_at,
                )
            except AFOSProductParseError as exc:
                logger.warning(
                    "Skipping malformed AFOS product | "
                    "pil=%s | product=%d | error=%s",
                    requested_pil,
                    product_number,
                    exc,
                )
                continue

            records.append(record)

        return records


    def _build_bronze_record(
        self,
        product_text: str,
        requested_pil: str,
        retrieved_at: datetime,
    ) -> BronzeRecord:
        header = self._parse_header(product_text)
        pil = header.get("pil") or requested_pil

        issued_at_text, published_at = self._parse_product_timestamp(
            product_text=product_text,
            pil=pil,
        )

        return BronzeRecord(
            source=self.name,
            record_id=self._make_source_record_id(
                pil=pil,
                header=header,
                published_at=published_at,
            ),
            published_at=published_at,
            retrieved_at=retrieved_at,
            raw={
                "pil": pil,
                "header": header,
                "issued_at_text": issued_at_text,
                "raw_text": product_text,
            },
        )


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



    def _parse_product_timestamp(
        self,
        product_text: str,
        pil: str,
    ) -> tuple[str, datetime]:
        """Extract and parse the product issuance timestamp."""
        timestamp_text = self._extract_product_timestamp_text(product_text)

        if timestamp_text is None:
            raise AFOSProductParseError(
                f"Missing product issuance timestamp for PIL={pil}"
            )

        try:
            published_at = self._parse_issued_at(timestamp_text)
        except ValueError as exc:
            raise AFOSProductParseError(
                f"Invalid product issuance timestamp for PIL={pil}: "
                f"{timestamp_text!r}"
            ) from exc

        return timestamp_text, published_at

    def _extract_product_timestamp_text(
        self,
        product_text: str,
    ) -> str | None:
        """Extract the top-level product timestamp text."""
        normalized_text = self._normalize_newlines(product_text)
        match = self.PRODUCT_TIMESTAMP_RE.search(normalized_text)

        if match is None:
            return None

        return match.group("issued_at").strip()

    def _parse_issued_at(self, text: str) -> datetime:
        """Parse an AFOS issuance timestamp into a UTC datetime."""
        cleaned = text.strip()

        if not cleaned:
            raise ValueError("Timestamp is empty")

        if cleaned.lower().startswith("issued at "):
            cleaned = cleaned[len("issued at "):].strip()

        if cleaned.lower().startswith("issued by"):
            raise ValueError("Text contains an issuer, not an issuance timestamp")

        parts = cleaned.split()

        if len(parts) < 5:
            raise ValueError(f"Incomplete AFOS timestamp: {text!r}")

        time_part = parts[0].zfill(4)
        has_ampm = parts[1].upper() in {"AM", "PM"}

        if has_ampm:
            am_pm = parts[1].upper()
            tz_abbr = parts[2].upper()
            weekday = _AFOS_WEEKDAY_FIXES.get(parts[3], parts[3])
            date_parts = parts[4:]

            normalized = (
                f"{time_part} {am_pm} "
                f"{weekday} {' '.join(date_parts)}"
            )
            timestamp_format = "%I%M %p %a %b %d %Y"
        else:
            tz_abbr = parts[1].upper()
            weekday = _AFOS_WEEKDAY_FIXES.get(parts[2], parts[2])
            date_parts = parts[3:]

            normalized = (
                f"{time_part} "
                f"{weekday} {' '.join(date_parts)}"
            )
            timestamp_format = "%H%M %a %b %d %Y"

        timezone_name = _AFOS_TZ_MAP.get(tz_abbr)

        if timezone_name is None:
            raise ValueError(
                f"Unsupported AFOS timezone abbreviation: {tz_abbr!r}"
            )

        parsed = datetime.strptime(normalized, timestamp_format)

        return (
            parsed.replace(tzinfo=ZoneInfo(timezone_name))
            .astimezone(timezone.utc)
        )
    
    def _make_source_record_id(
        self,
        pil: str,
        header: dict[str, str | None],
        published_at: str,
    ) -> str:
        fingerprint = stable_hash(
            {
                "source": self.name,
                "pil": pil,
                "office": header.get("office"),
                "issued_code": header.get("issued_code"),
                "raw_id": header.get("raw_id"),
                "published_at": published_at,
            }
        )

        return f"iem::{fingerprint}"

    
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
        issued_at_text = self._extract_section_issued_text(content)

        cleaned = self.SECTION_TIMESTAMP_RE.sub("", content)
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



    def _extract_section_issued_text(
        self,
        text: str,
    ) -> str | None:
        match = self.SECTION_TIMESTAMP_RE.search(
            self._normalize_newlines(text)
        )
        if match is None:
            return None

        return match.group("issued_at").strip()

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
    # Shared Utilities
    # ------------------------------------------------------------------

    
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