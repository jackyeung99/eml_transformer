
import pandas as pd


def aggregate_hourly_severity(
    df: pd.DataFrame,
    *,
    time_column: str = "observed_at",
    group_columns: tuple[str, ...] = ("source", "region"),
) -> pd.DataFrame:
    result = df.copy()

    result["hour"] = (
        pd.to_datetime(result[time_column], utc=True)
        .dt.floor("h")
    )

    hourly = (
        result.groupby(
            [*group_columns, "hour"],
            dropna=False,
        )
        .agg(
            document_count=("severity_score", "size"),
            severity_mean=("severity_score", "mean"),
            severity_max=("severity_score", "max"),
            severe_document_count=(
                "severity_score",
                lambda values: (values >= 0.7).sum(),
            ),
        )
        .reset_index()
        .rename(columns={"hour": "observed_at"})
    )

    return hourly

IEM_PRODUCT_SEVERITY = {
    "AFD": 0.10,  # Area Forecast Discussion
    "HWO": 0.30,  # Hazardous Weather Outlook
    "SPS": 0.40,  # Special Weather Statement
    "LSR": 0.55,  # Local Storm Report
    "WSW": 0.70,  # Winter Storm Warning/Watch
    "NPW": 0.75,  # Non-Precipitation Warning
}

SEVERITY_TERMS = {
    "advisory": 0.15,
    "watch": 0.30,
    "warning": 0.50,
    "significant": 0.20,
    "severe": 0.30,
    "extreme": 0.40,
    "dangerous": 0.30,
    "life threatening": 0.50,
    "widespread": 0.20,
    "major": 0.25,
}

def add_iem_severity(
    df: pd.DataFrame,
    *,
    product_column: str = "product",
    text_column: str = "text",
) -> pd.DataFrame:
    result = df.copy()

    product_score = (
        result[product_column]
        .astype("string")
        .str.upper()
        .map(IEM_PRODUCT_SEVERITY)
        .fillna(0.0)
    )

    text = result[text_column].fillna("").str.lower()

    language_score = pd.Series(0.0, index=result.index)

    for term, weight in SEVERITY_TERMS.items():
        language_score += text.str.contains(
            term,
            regex=False,
        ).astype(float) * weight

    # Cap language contribution so repeated keywords do not dominate.
    language_score = language_score.clip(upper=0.5)

    result["severity_score"] = (
        product_score + language_score
    ).clip(0.0, 1.0)

    return result


GDELT_SEVERE_TERMS = {
    "power outage": 0.40,
    "grid emergency": 0.50,
    "energy emergency": 0.50,
    "rolling blackout": 0.50,
    "load shedding": 0.50,
    "extreme heat": 0.35,
    "heat wave": 0.30,
    "winter storm": 0.30,
    "extreme cold": 0.35,
    "polar vortex": 0.35,
    "natural gas shortage": 0.40,
    "pipeline outage": 0.40,
    "generation outage": 0.40,
}

def add_gdelt_severity(
    df: pd.DataFrame,
    *,
    text_column: str = "text",
    tone_column: str = "tone",
) -> pd.DataFrame:
    result = df.copy()
    text = result[text_column].fillna("").str.lower()

    keyword_score = pd.Series(0.0, index=result.index)

    for term, weight in GDELT_SEVERE_TERMS.items():
        keyword_score += text.str.contains(
            term,
            regex=False,
        ).astype(float) * weight

    keyword_score = keyword_score.clip(upper=0.8)

    # Assumes conventional GDELT tone, where negative values are negative tone.
    tone = pd.to_numeric(
        result[tone_column],
        errors="coerce",
    ).fillna(0.0)

    negative_tone_score = (
        (-tone).clip(lower=0, upper=10) / 10
    )

    # Tone modifies relevant events but cannot independently create severity.
    result["severity_score"] = (
        keyword_score * (0.75 + 0.25 * negative_tone_score)
    ).clip(0.0, 1.0)

    result["severity_method"] = "gdelt_rules_v1"

    return result