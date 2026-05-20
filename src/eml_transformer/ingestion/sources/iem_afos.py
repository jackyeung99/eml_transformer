from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import requests

from eml_transformer.ingestion.base import TextSource
from eml_transformer.ingestion.registry import register_source
from eml_transformer.ingestion.schema import TextRecord
from eml_transformer.utils.stamping import stable_hash


@register_source("iem_afos")
class IEMAFOSSource(TextSource):
    """
    Ingest archived NWS text products from the Iowa Environmental Mesonet
    AFOS archive.

    This source can ingest one specific PIL, such as AFDIND, or many PILs
    formed from product_types x WFOs.

    Examples:
        AFDIND, HWOIND, NPWIND, LSRIND, WSWIND
        AFDLOT, HWOLOT, NPWLOT, LSRLOT, WSWLOT


    Reference: https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?help 
    """

    name = "iem_afos"
    source_type = "api"
    update_mode = "incremental"
    supports_backfill = True

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
        "JAN",  # Jackson MS
        "LIX",  # New Orleans / Baton Rouge
        "MOB",  # Mobile
        "BMX",  # Birmingham
    ]

    DEFAULT_PRODUCT_TYPES = [
        "AFD",  # Area Forecast Discussion
        "HWO",  # Hazardous Weather Outlook
        "NPW",  # Non-precipitation warnings: heat, cold, wind, fog
        "WSW",  # Winter storm watches/warnings/advisories
        "LSR",  # Local storm reports
        "SPS",  # Special weather statements
    ]

    def __init__(
        self,
        pil: str | None = None,
        wfos: list[str] | None = None,
        product_types: list[str] | None = None,
        limit: int = 100,
        fmt: str = "text",
        timeout: int = 30,
    ):
        self.pil = pil.upper() if pil else None
        self.wfos = [
            wfo.upper()
            for wfo in (wfos or self.DEFAULT_MISO_WFOS)
        ]
        self.product_types = [
            product_type.upper()
            for product_type in (
                product_types or self.DEFAULT_PRODUCT_TYPES
            )
        ]

        self.limit = limit
        self.fmt = fmt
        self.timeout = timeout

        self.base_url = (
            "https://mesonet.agron.iastate.edu/"
            "cgi-bin/afos/retrieve.py"
        )

    def fetch_raw(
        self,
        sdate: str,
        edate: str,
    ) -> dict[str, str]:
        results: dict[str, str] = {}

        for pil in self._pils_to_fetch():
            params = {
                "pil": pil,
                "sdate": sdate,
                "edate": edate,
                "limit": self.limit,
                "fmt": self.fmt,
            }

            response = requests.get(
                self.base_url,
                params=params,
                timeout=self.timeout,
            )

            response.raise_for_status()

            text = response.text.strip()

            if not text or text.startswith("ERROR:"):
                continue

            results[pil] = text

        return results

    def parse_records(
        self,
        raw: dict[str, str],
    ) -> list[TextRecord]:
        records: list[TextRecord] = []

        for fallback_pil, raw_text in raw.items():
            for chunk in self._split_products(raw_text):
                parsed = self._parse_product(
                    text=chunk,
                    fallback_pil=fallback_pil,
                )

                record_id = stable_hash(
                    {
                        "source": self.name,
                        "pil": parsed["pil"],
                        "office": parsed["office"],
                        "wmo_header": parsed["wmo_header"],
                        "issued_at_text": parsed["issued_at_text"],
                    }
                )

                record = TextRecord(
                    record_id=record_id,
                    source=self.name,
                    source_type=self.source_type,
                    title=parsed["title"],
                    text=parsed["full_text"],
                    published_at=parsed["issued_at_text"],
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    url=parsed["url"],
                    region=parsed["office"],
                    categories=parsed["categories"],
                    raw=parsed,
                )

                records.append(record)

        return records
    
    def standardize_record(
        self,
        record: TextRecord,
    ) -> TextRecord:
        key_messages = self._extract_key_messages(record.text)

        published_at = self._parse_issued_at(record.published_at)

        data = {
            **record.__dict__,
            "text": key_messages or record.text,
            "published_at": published_at,
        }

        raw = dict(record.raw or {})
        raw["standardized_text_source"] = "key_messages"
        raw["full_text"] = record.text
        raw["published_at_standardized"] = published_at

        data["raw"] = raw

        return TextRecord(**data)

    def _pils_to_fetch(self) -> list[str]:
        if self.pil:
            return [self.pil]

        return [
            f"{product_type}{wfo}"
            for product_type in self.product_types
            for wfo in self.wfos
        ]

    def _split_products(
        self,
        raw: str,
    ) -> list[str]:
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")

        pattern = (
            r"(?m)(?=^\d{3}\n"
            r"[A-Z]{4}\d{2}\s+K[A-Z]{3}\s+\d{6}\n"
            r"[A-Z]{3}[A-Z0-9]{3})"
        )

        chunks = re.split(pattern, raw)

        return [
            chunk.strip()
            for chunk in chunks
            if chunk.strip()
            and not chunk.strip().startswith("ERROR:")
        ]

    def _parse_product(
        self,
        text: str,
        fallback_pil: str,
    ) -> dict[str, Any]:

        header = self._parse_header(text)

        pil = header.get("pil") or fallback_pil
        product_type = pil[:3]

        issued_at_text = self._extract_issued_text(text)

        key_messages = self._extract_key_messages(text)

        return {
            "pil": pil,
            "product_type": product_type,
            "raw_id": header.get("raw_id"),
            "wmo_header": header.get("wmo_header"),
            "office": header.get("office"),
            "issued_code": header.get("issued_code"),
            "issued_at_text": issued_at_text,
            "title": self._make_title(
                product_type=product_type,
                office=header.get("office"),
                issued_at_text=issued_at_text,
            ),
            "text": key_messages,
            "full_text": text,
            "url": self.base_url,
            "categories": [
                "weather",
                "nws",
                "iem",
                "afos",
                product_type.lower(),
            ],
        }

    def _parse_header(
        self,
        text: str,
    ) -> dict[str, str | None]:
        match = re.search(
            r"(?m)^(\d{3})\n"
            r"([A-Z]{4}\d{2}\s+(K[A-Z]{3})\s+(\d{6}))\n"
            r"([A-Z]{3}[A-Z0-9]{3})",
            text,
        )

        if not match:
            return {
                "raw_id": None,
                "wmo_header": None,
                "office": None,
                "issued_code": None,
                "pil": None,
            }

        return {
            "raw_id": match.group(1),
            "wmo_header": match.group(2),
            "office": match.group(3),
            "issued_code": match.group(4),
            "pil": match.group(5),
        }

    def _extract_issued_text(
        self,
        text: str,
    ) -> str | None:
        match = re.search(
            r"(?m)^Issued at .+$",
            text,
        )

        if match:
            return match.group(0).strip()

        match = re.search(
            r"(?m)^National Weather Service .*\n(.+)$",
            text,
        )

        if not match:
            return None

        return match.group(1).strip()

    def _parse_issued_at(
        self,
        issued_at_text: str | None,
    ) -> str | None:
        if not issued_at_text:
            return None

        cleaned = issued_at_text.strip()

        if cleaned.lower().startswith("issued at "):
            cleaned = cleaned[len("Issued at "):]

        try:
            dt = parsedate_to_datetime(cleaned)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.isoformat()

        except Exception:
            return cleaned

    def _extract_key_messages(
        self,
        text: str,
    ) -> str | None:
        pattern = (
            r"(?s)\.KEY MESSAGES\.\.\.\s*\n"
            r"(.*?)(?=\n&&|\n\.[A-Z]|\n\$\$|\Z)"
        )

        match = re.search(pattern, text)

        if not match:
            return None

        return match.group(1).strip()

    def _make_title(
        self,
        product_type: str,
        office: str | None,
        issued_at_text: str | None,
    ) -> str:
        parts = [
            product_type,
            office or "",
            issued_at_text or "",
        ]
