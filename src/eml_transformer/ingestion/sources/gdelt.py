from __future__ import annotations

import logging
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

import pandas as pd
import requests

from eml_transformer.ingestion.base import TextSource
from eml_transformer.ingestion.registry import register_source
from eml_transformer.ingestion.schema import BronzeRecord, TextRecord
from eml_transformer.utils.dates import utc_now

logger = logging.getLogger(__name__)


GKG_COLUMNS = [
    "GKGRECORDID",
    "DATE",
    "SourceCollectionIdentifier",
    "SourceCommonName",
    "DocumentIdentifier",
    "Counts",
    "V2Counts",
    "Themes",
    "V2Themes",
    "Locations",
    "V2Locations",
    "Persons",
    "V2Persons",
    "Organizations",
    "V2Organizations",
    "Tone",
    "Dates",
    "GCAM",
    "SharingImage",
    "RelatedImages",
    "SocialImageEmbeds",
    "SocialVideoEmbeds",
    "Quotations",
    "AllNames",
    "Amounts",
    "TranslationInfo",
    "Extras",
]


class GDELTRecordParseError(ValueError):
    """Raised when a GDELT row cannot become a bronze record."""


@register_source("gdelt")
class GDELTSource(TextSource):
    """Ingest GDELT GKG records.

    Ingestion downloads GKG files, applies source-specific filters, and
    constructs bronze records. Standardization converts bronze records into
    the common TextRecord schema used in silver.
    """

    name = "gdelt"
    source_type = "api"
    update_mode = "incremental"
    supports_backfill = True
    default_lookback_days = 1

    BASE_URL = "http://data.gdeltproject.org/gdeltv2"
    MAX_WORKERS = 8
    REQUEST_TIMEOUT = 60

    PAGE_TITLE_RE = re.compile(
        r"<PAGE_TITLE>(.*?)</PAGE_TITLE>",
        flags=re.DOTALL,
    )

    PRECISE_TIMESTAMP_RE = re.compile(
        r"<PAGE_PRECISEPUBTIMESTAMP>"
        r"(.*?)"
        r"</PAGE_PRECISEPUBTIMESTAMP>",
        flags=re.DOTALL,
    )

    def __init__(
        self,
        target_themes: set[str] | None = None,
        target_locations: set[str] | None = None,
        target_organizations: set[str] | None = None,
        min_theme_matches: int = 2,
        session: requests.Session | None = None,
        max_workers: int = MAX_WORKERS,
        timeout: int = REQUEST_TIMEOUT,
    ) -> None:
        self.target_themes = self._normalize_values(target_themes)
        self.target_locations = self._normalize_values(target_locations)
        self.target_organizations = self._normalize_values(
            target_organizations
        )

        self.min_theme_matches = min_theme_matches
        self.max_workers = max_workers
        self.timeout = timeout
        self._session = session or requests.Session()

    # ------------------------------------------------------------------
    # Public pipeline interface
    # ------------------------------------------------------------------

    def fetch_records(
        self,
        from_date: datetime,
        to_date: datetime,
    ) -> list[BronzeRecord]:
        logger.info(
            "Starting GDELT fetch | from_date=%s | to_date=%s",
            from_date,
            to_date,
        )

        timestamps = self._get_timestamps(
            from_date=from_date,
            to_date=to_date,
        )

        frames, total_records_seen = self._fetch_files(timestamps)

        bronze_records = self._build_bronze_records(frames)

        logger.info(
            (
                "Finished GDELT fetch | files=%d | raw=%d "
                "| bronze=%d | removed=%d"
            ),
            len(timestamps),
            total_records_seen,
            len(bronze_records),
            total_records_seen - len(bronze_records),
        )

        return bronze_records

    def standardize_record(
        self,
        record: BronzeRecord,
    ) -> TextRecord:
        raw = record.raw

        themes = self._split_values(raw.get("Themes"))
        organizations = self._split_values(raw.get("Organizations"))
        persons = self._split_values(raw.get("Persons"))
        locations = sorted(
            self._parse_locations(raw.get("Locations"))
        )

        has_precise_timestamp = bool(
            self._extract_precise_timestamp(raw)
        )

        return TextRecord(
            record_id=record.record_id,
            source=record.source,
            source_type=self.source_type,
            title=self._extract_page_title(raw),
            text="",
            published_at=record.published_at,
            retrieved_at=record.retrieved_at,
            url=raw.get("DocumentIdentifier"),
            region=locations[0] if locations else None,
            categories=themes,
            metadata={
                "source_common_name": raw.get("SourceCommonName"),
                "published_at": {
                    "source": (
                        "page_metadata"
                        if has_precise_timestamp
                        else "gdelt"
                    ),
                    "precision": (
                        "second"
                        if has_precise_timestamp
                        else "15min"
                    ),
                },
                "organizations": organizations,
                "persons": persons,
                "locations": locations,
                "tone": raw.get("Tone"),
                "filter": {
                    "theme_match": raw.get("theme_match"),
                    "organization_match": raw.get(
                        "organization_match"
                    ),
                    "location_match": raw.get("location_match"),
                    "match_count": raw.get("filter_match_count"),
                },
            },
            raw=raw,
        )

    # ------------------------------------------------------------------
    # File discovery
    # ------------------------------------------------------------------

    def _get_timestamps(
        self,
        from_date: datetime,
        to_date: datetime,
    ) -> list[str]:
        start = pd.Timestamp(from_date).floor("15min")
        requested_end = pd.Timestamp(to_date).floor("15min")

        latest_available = (
            pd.Timestamp.now(tz="UTC").floor("15min")
            - pd.Timedelta(minutes=30)
        )

        end = min(requested_end, latest_available)

        if start >= end:
            return []

        return (
            pd.date_range(
                start=start,
                end=end,
                freq="15min",
                inclusive="left",
            )
            .strftime("%Y%m%d%H%M%S")
            .tolist()
        )

    def _build_file_url(self, timestamp: str) -> str:
        return f"{self.BASE_URL}/{timestamp}.gkg.csv.zip"

    # ------------------------------------------------------------------
    # API/file access
    # ------------------------------------------------------------------

    def _fetch_files(
        self,
        timestamps: list[str],
    ) -> tuple[list[pd.DataFrame], int]:
        if not timestamps:
            return [], 0

        frames: list[pd.DataFrame] = []
        total_records_seen = 0
        failed_files = 0

        worker_count = min(self.max_workers, len(timestamps))

        logger.info(
            "Downloading GDELT files | files=%d | workers=%d",
            len(timestamps),
            worker_count,
        )

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(self._fetch_file, timestamp): timestamp
                for timestamp in timestamps
            }

            for future in as_completed(futures):
                timestamp = futures[future]

                try:
                    frame, total_records = future.result()
                except Exception:
                    failed_files += 1
                    logger.warning(
                        "GDELT file failed | timestamp=%s",
                        timestamp,
                        exc_info=True,
                    )
                    continue

                total_records_seen += total_records

                if not frame.empty:
                    frames.append(frame)

        logger.info(
            (
                "Finished GDELT downloads | files=%d "
                "| failed=%d | filtered_rows=%d"
            ),
            len(timestamps),
            failed_files,
            sum(len(frame) for frame in frames),
        )

        return frames, total_records_seen

    def _fetch_file(
        self,
        timestamp: str,
    ) -> tuple[pd.DataFrame, int]:
        url = self._build_file_url(timestamp)

        response = self._session.get(
            url,
            timeout=self.timeout,
        )
        response.raise_for_status()

        frame = self._read_gkg_archive(response.content)
        frame["GDELT_TIMESTAMP"] = timestamp
        frame["GDELT_URL"] = url

        filtered = self._filter_records(frame)

        return filtered, len(frame)

    @staticmethod
    def _read_gkg_archive(content: bytes) -> pd.DataFrame:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            filenames = archive.namelist()

            if not filenames:
                raise ValueError("GDELT archive contains no files")

            frame = pd.read_csv(
                archive.open(filenames[0]),
                sep="\t",
                header=None,
                dtype=str,
                low_memory=False,
                encoding="latin1",
            )

        if len(frame.columns) > len(GKG_COLUMNS):
            raise ValueError(
                "GDELT file contains more columns than expected: "
                f"{len(frame.columns)} > {len(GKG_COLUMNS)}"
            )

        frame.columns = GKG_COLUMNS[: len(frame.columns)]
        return frame

    # ------------------------------------------------------------------
    # Bronze construction
    # ------------------------------------------------------------------

    def _build_bronze_records(
        self,
        frames: list[pd.DataFrame],
    ) -> list[BronzeRecord]:
        records: list[BronzeRecord] = []

        for frame in frames:
            records.extend(self._build_records_from_frame(frame))

        return self._deduplicate_records(records)

    def _build_records_from_frame(
        self,
        frame: pd.DataFrame,
    ) -> list[BronzeRecord]:
        records: list[BronzeRecord] = []
        retrieved_at = utc_now()

        for row_number, row in enumerate(
            frame.to_dict(orient="records"),
            start=1,
        ):
            try:
                record = self._build_bronze_record(
                    row=row,
                    retrieved_at=retrieved_at,
                )
            except GDELTRecordParseError as exc:
                logger.warning(
                    (
                        "Skipping malformed GDELT row "
                        "| row=%d | error=%s"
                    ),
                    row_number,
                    exc,
                )
                continue

            records.append(record)

        return records

    def _build_bronze_record(
        self,
        row: dict[str, Any],
        retrieved_at: datetime,
    ) -> BronzeRecord:
        record_id = self._require_text(row, "GKGRECORDID")

        precise_timestamp = self._extract_precise_timestamp(row)
        fallback_timestamp = (
            row.get("GDELT_TIMESTAMP")
            or row.get("DATE")
        )

        try:
            published_at = self._parse_gdelt_timestamp(
                precise_timestamp or fallback_timestamp
            )
        except (TypeError, ValueError) as exc:
            raise GDELTRecordParseError(
                f"Invalid timestamp for GKGRECORDID={record_id}"
            ) from exc

        return BronzeRecord(
            source=self.name,
            record_id=f"gdelt::{record_id}",
            published_at=published_at,
            retrieved_at=retrieved_at,
            raw=self._clean_raw_row(row),
        )

    @staticmethod
    def _clean_raw_row(
        row: dict[str, Any],
    ) -> dict[str, Any]:
        """Replace pandas missing values with JSON-compatible None."""

        return {
            key: None if pd.isna(value) else value
            for key, value in row.items()
        }

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _filter_records(
        self,
        records: pd.DataFrame,
    ) -> pd.DataFrame:
        if records.empty:
            return records

        filtered = records.copy()

        theme_match, theme_counts = self._filter_themes(filtered)

        filtered["theme_match"] = theme_match
        filtered["theme_match_count"] = theme_counts
        filtered["organization_match"] = self._filter_organizations(
            filtered
        )
        filtered["location_match"] = self._filter_locations(filtered)

        criteria = (
            filtered["theme_match"]
            & filtered["location_match"]
        ) | filtered["organization_match"]

        result = filtered.loc[criteria].copy()

        logger.debug(
            (
                "Filtered GDELT records | input=%d | output=%d "
                "| themes=%d | organizations=%d | locations=%d"
            ),
            len(filtered),
            len(result),
            int(filtered["theme_match"].sum()),
            int(filtered["organization_match"].sum()),
            int(filtered["location_match"].sum()),
        )

        return result


    def _filter_themes(
        self,
        records: pd.DataFrame,
    ) -> tuple[pd.Series, pd.Series]:
        theme_counts = records["Themes"].apply(
            lambda value: len(
                self._parse_themes(value)
                & self.target_themes
            )
        )

        theme_matches = theme_counts >= self.min_theme_matches

        return theme_matches, theme_counts
    
    def _filter_organizations(
        self,
        records: pd.DataFrame,
    ) -> pd.Series:
        return records["V2Organizations"].apply(
            lambda value: bool(
                self._parse_organizations(value)
                & self.target_organizations
            )
        )

    def _filter_locations(
        self,
        records: pd.DataFrame,
    ) -> pd.Series:
        return records["V2Locations"].apply(
            lambda value: bool(
                self._parse_locations(value)
                & self.target_locations
            )
        )


    # ------------------------------------------------------------------
    # Parsing utilities
    # ------------------------------------------------------------------

    def _extract_page_title(
        self,
        record: dict[str, Any],
    ) -> str:
        return self._extract_extras_value(
            record=record,
            pattern=self.PAGE_TITLE_RE,
        )

    def _extract_precise_timestamp(
        self,
        record: dict[str, Any],
    ) -> str:
        return self._extract_extras_value(
            record=record,
            pattern=self.PRECISE_TIMESTAMP_RE,
        )

    @staticmethod
    def _extract_extras_value(
        record: dict[str, Any],
        pattern: re.Pattern[str],
    ) -> str:
        extras = record.get("Extras")

        if not isinstance(extras, str):
            return ""

        match = pattern.search(extras)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _parse_gdelt_timestamp(
        value: Any,
    ) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("GDELT timestamp is missing")

        parsed = datetime.strptime(
            value.strip(),
            "%Y%m%d%H%M%S",
        )

        return parsed.replace(tzinfo=timezone.utc)

    @staticmethod
    def _parse_themes(value: Any) -> set[str]:
        return {
            item.upper()
            for item in GDELTSource._split_values(value)
        }

    @staticmethod
    def _parse_organizations(value: Any) -> set[str]:
        if not isinstance(value, str):
            return set()

        return {
            organization.split(",", 1)[0].strip().upper()
            for organization in value.split(";")
            if organization.strip()
        }

    @staticmethod
    def _parse_locations(value: Any) -> set[str]:
        if not isinstance(value, str):
            return set()

        locations: set[str] = set()

        for location in value.split(";"):
            parts = location.split("#")

            country = parts[2].strip().upper() if len(parts) > 2 else ""
            region = parts[3].strip().upper() if len(parts) > 3 else ""

            if country:
                locations.add(country)

            if region:
                locations.add(region)

            if country and region:
                locations.add(f"{country}-{region}")

        return locations

    @staticmethod
    def _split_values(value: Any) -> list[str]:
        if not isinstance(value, str):
            return []

        return [
            item.strip()
            for item in value.split(";")
            if item.strip()
        ]

    @staticmethod
    def _require_text(
        record: dict[str, Any],
        field: str,
    ) -> str:
        value = record.get(field)

        if not isinstance(value, str) or not value.strip():
            raise GDELTRecordParseError(
                f"Missing required field {field!r}"
            )

        return value.strip()

    @staticmethod
    def _normalize_values(
        values: set[str] | None,
    ) -> set[str]:
        return {
            value.strip().upper()
            for value in (values or set())
            if value.strip()
        }