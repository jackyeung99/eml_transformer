from eml_transformer.ingestion.sources.gdelt import GDELTSource



def test_parse_themes_returns_uppercase_set(gdelt_source):
    result = gdelt_source._parse_themes("POWER;grid")

    assert result == {"POWER", "GRID"}

def test_parse_organizations(gdelt_source):
    orgs = 'spacex;new york times;chinese communist party;u s army'
    result = gdelt_source._parse_organizations(orgs)

    assert result == {
        "SPACEX",
        "NEW YORK TIMES",
        "CHINESE COMMUNIST PARTY",
        "U S ARMY"
    }


def test_parse_locations_returns_country_adm1_and_combined_key(gdelt_source):
    value = "2#Indiana#US#IN#39.7#-86.1#IN"

    result = gdelt_source._parse_locations(value)

    assert result == {
        "US",
        "IN",
        "US-IN",
    }

def test_parse_multi_location(gdelt_source):
    value = (
        "4#Shanghai, Shanghai, China#CH#CH23#31.2222#121.458#-1924465;"
        "2#New York, United States#US#USNY#42.1497#-74.9384#NY;"
        "1#China#CH#CH#35#105#CH"
    )

    result = gdelt_source._parse_locations(value)

    assert result == {
        "CH",
        "CH23",
        "CH-CH23",
        "US",
        "USNY",
        "US-USNY",
        "CH-CH",
    }

def test_parse_locations_handles_missing_value(gdelt_source):
    assert gdelt_source._parse_locations(None) == set()

