from eml_transformer.ingestion.sources.gdelt import GDELTSource


# THEMES
def test_parse_themes_returns_uppercase_set(gdelt_source):
    result = gdelt_source._parse_themes("POWER;grid")

    assert result == {"POWER", "GRID"}

def test_parse_multi_themes(gdelt_source):
    result = gdelt_source._parse_themes("power;")

    assert result == {"POWER"}

def test_parse_multi_themes(gdelt_source):
    result = gdelt_source._parse_themes("power;grid;electricity")

    assert result == {"POWER", "GRID", "ELECTRICITY"}

def test_parse_empty_themes(gdelt_source):
    result = gdelt_source._parse_themes("")

    assert result == set()


# ORGANIZATIONS
def test_parse_organizations(gdelt_source):
    orgs = 'spacex;new york times;chinese communist party;u s army'
    result = gdelt_source._parse_organizations(orgs)

    assert result == {
        "SPACEX",
        "NEW YORK TIMES",
        "CHINESE COMMUNIST PARTY",
        "U S ARMY"
    }

def test_parse_duplicate_organizations(gdelt_source):
    orgs = 'spacex;spacex'
    result = gdelt_source._parse_organizations(orgs)

    assert result == {
        "SPACEX"
    }

# LOCATIONS 
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



# META DATA Extraction
def test_extract_page_title(gdelt_source):
    record = {
        "Extras": """
<PAGE_TITLE>Major Power Outage Hits Indiana</PAGE_TITLE>
<PAGE_PRECISEPUBTIMESTAMP>20260101123045</PAGE_PRECISEPUBTIMESTAMP>
"""
    }

    assert (
        gdelt_source._extract_page_title(record)
        == "Major Power Outage Hits Indiana"
    )

def test_extract_page_title_missing_tag(gdelt_source):
    record = {"Extras": ""}

    assert gdelt_source._extract_page_title(record) == ""

def test_extract_page_title_missing_extras(gdelt_source):
    assert gdelt_source._extract_page_title({}) == ""
    
def test_extract_page_title_strips_whitespace(gdelt_source):
    record = {
        "Extras": """
<PAGE_TITLE>
    Major Power Outage Hits Indiana
</PAGE_TITLE>
"""
    }

    assert (
        gdelt_source._extract_page_title(record)
        == "Major Power Outage Hits Indiana"
    )

def test_extract_page_title_malformed_missing_closing_tag(gdelt_source):
    record = {
        "Extras": "<PAGE_TITLE>Major Power Outage Hits Indiana"
    }

    assert gdelt_source._extract_page_title(record) == ""

def test_extract_page_title_malformed_missing_opening_tag(gdelt_source):
    record = {
        "Extras": "Major Power Outage Hits Indiana</PAGE_TITLE>"
    }

    assert gdelt_source._extract_page_title(record) == ""

def test_extract_precise_time(gdelt_source):
    record = {
        "Extras": """
<PAGE_TITLE>Major Power Outage Hits Indiana</PAGE_TITLE>
<PAGE_PRECISEPUBTIMESTAMP>20260101123045</PAGE_PRECISEPUBTIMESTAMP>
"""
    }

    assert (
        gdelt_source._extract_precise_timestamp(record)
        == "20260101123045"
    )

def test_extract_page_title_malformed_mismatched_tag(gdelt_source):
    record = {
        "Extras": "<PAGE_TITLE>Major Power Outage Hits Indiana</TITLE>"
    }

    assert gdelt_source._extract_page_title(record) == ""

def test_extract_precise_time_malformed_missing_closing_tag(gdelt_source):
    record = {
        "Extras": "<PAGE_PRECISEPUBTIMESTAMP>20260101123045"
    }

    assert gdelt_source._extract_precise_timestamp(record) == ""

def test_extract_precise_time_malformed_missing_opening_tag(gdelt_source):
    record = {
        "Extras": "20260101123045</PAGE_PRECISEPUBTIMESTAMP>"
    }

    assert gdelt_source._extract_precise_timestamp(record) == ""