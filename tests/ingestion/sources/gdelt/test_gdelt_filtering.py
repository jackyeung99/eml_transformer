
import pandas as pd

from eml_transformer.ingestion.sources.gdelt import GDELTSource


def test_filter_themes_requires_minimum_number_of_matches():
    source = GDELTSource(
        target_themes={"POWER", "GRID", "WEATHER"},
        min_filter_matches=2,
    )

    df = pd.DataFrame(
        {
            "Themes": [
                "POWER;GRID",
                "POWER",
                "OTHER;NEWS",
                None,
            ]
        }
    )

    result = source._filter_themes(df, required_themes=2)

    assert result.tolist() == [True, False, False, False]


def test_filter_themes_is_case_insensitive_and_strips_whitespace():
    source = GDELTSource(
        target_themes={"POWER", "GRID"},
    )

    df = pd.DataFrame(
        {
            "Themes": [
                " power ; grid ",
                " POWER ",
                "weather",
            ]
        }
    )

    result = source._filter_themes(df, required_themes=1)

    assert result.tolist() == [True, True, False]


def test_filter_organizations_matches_v2_organization_names():
    source = GDELTSource(
        target_organizations={"MISO", "PJM INTERCONNECTION"},
    )

    df = pd.DataFrame(
        {
            "V2Organizations": [
                "MISO,123",
                "PJM Interconnection,456",
                "OTHER ORG,789",
                None,
            ]
        }
    )

    result = source._filter_organizations(df)

    assert result.tolist() == [True, True, False, False]


def test_filter_locations_matches_country_adm1_or_combined_key():
    source = GDELTSource(
        target_locations={"US-IN", "USNY", "CH"},
    )

    df = pd.DataFrame(
        {
            "V2Locations": [
                "2#Indiana, United States#US#IN#39.7#-86.1#IN",
                "2#New York, United States#US#USNY#42.1#-74.9#NY",
                "1#China#CH#CH#35#105#CH",
                "2#Texas, United States#US#TX#31.0#-99.0#TX",
                None,
            ]
        }
    )

    result = source._filter_locations(df)

    assert result.tolist() == [True, True, True, False, False]


def test_filter_records_keeps_theme_and_location_match():
    source = GDELTSource(
        target_themes={"POWER", "GRID"},
        target_locations={"US-IN"},
        target_organizations={"MISO"},
        min_filter_matches=2,
    )

    df = pd.DataFrame(
        [
            {
                "GKGRECORDID": "theme-location-match",
                "Themes": "POWER;GRID",
                "V2Organizations": "",
                "V2Locations": "2#Indiana, United States#US#IN#39.7#-86.1#IN",
            },
            {
                "GKGRECORDID": "theme-only-no-location",
                "Themes": "POWER;GRID",
                "V2Organizations": "",
                "V2Locations": "2#Texas, United States#US#TX#31.0#-99.0#TX",
            },
        ]
    )

    result = source._filter_records(df)

    assert result["GKGRECORDID"].tolist() == [
        "theme-location-match",
    ]


def test_filter_records_keeps_organization_match_even_without_theme_or_location():
    source = GDELTSource(
        target_themes={"POWER", "GRID"},
        target_locations={"US-IN"},
        target_organizations={"MISO"},
        min_filter_matches=2,
    )

    df = pd.DataFrame(
        [
            {
                "GKGRECORDID": "organization-match",
                "Themes": "OTHER",
                "V2Organizations": "MISO,123",
                "V2Locations": "",
            },
            {
                "GKGRECORDID": "no-match",
                "Themes": "OTHER",
                "V2Organizations": "OTHER ORG,456",
                "V2Locations": "",
            },
        ]
    )

    result = source._filter_records(df)

    assert result["GKGRECORDID"].tolist() == [
        "organization-match",
    ]


def test_filter_records_rejects_location_match_without_enough_themes():
    source = GDELTSource(
        target_themes={"POWER", "GRID"},
        target_locations={"US-IN"},
        target_organizations={"MISO"},
        min_filter_matches=2,
    )

    df = pd.DataFrame(
        [
            {
                "GKGRECORDID": "location-only",
                "Themes": "POWER",
                "V2Organizations": "",
                "V2Locations": "2#Indiana, United States#US#IN#39.7#-86.1#IN",
            },
        ]
    )

    result = source._filter_records(df)

    assert result.empty