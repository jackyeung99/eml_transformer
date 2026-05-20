from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import requests


GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def test_gdelt(
    query: str,
    days_back: int = 30,
    max_records: int = 100,
    out_path: str = "data/samples/gdelt_sample.csv",
):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)

    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": max_records,
        "sort": "hybridrel",
        "startdatetime": start.strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.strftime("%Y%m%d%H%M%S"),
    }

    url = f"{GDELT_DOC_URL}?{urlencode(params)}"
    print(f"Requesting:\n{url}\n")

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    print(response)
    data = response.json()
    articles = data.get("articles", [])

    print(f"Articles returned: {len(articles)}")

    if not articles:
        print("No articles found.")
        return pd.DataFrame()

    df = pd.DataFrame(articles)

    keep_cols = [
        "seendate",
        "title",
        "url",
        "domain",
        "language",
        "sourcecountry",
        "socialimage",
    ]
    df = df[[c for c in keep_cols if c in df.columns]]

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    print(f"Saved sample to: {out_path}")
    print(df.head(10).to_string(index=False))

    return df


if __name__ == "__main__":
    query = """
    Midcontinent Independent System Operator
    """

    test_gdelt(query=query, days_back=30, max_records=20)