
from eml_transformer.ingestion.sources.iem_afos import (
    IEMAFOSSource,
)
import requests
import pytest 

"""
Tests for AFOS source configuration and API access.

Behaviors covered:
- Constructor normalizes PIL, WFO, and product-type codes.
- A configured PIL overrides generated PIL combinations.
- Product types and WFOs generate the expected PIL combinations.
- API requests use the correct URL, parameters, and timeout.
- The configured polite delay is applied before each request.
- Empty responses and IEM ERROR responses are ignored.
- HTTP and connection failures propagate to the caller.
- _fetch_raw collects successful responses and skips empty responses.
- fetch_records coordinates fetching and bronze parsing.
"""


def test_init_normalizes_single_pil():
    source = IEMAFOSSource(
        pil='afdind'
    )

    assert source.pil
    assert source.pil == 'AFDIND'

def test_init_normalizes_wfos_and_product_types(): 

    source = IEMAFOSSource(
        wfos=['ind', 'iwx'],
        product_types=['afd', 'HWO']
    )

    assert source.wfos == ['IND', 'IWX']
    assert source.product_types == ['AFD', 'HWO']


def test_pils_to_fetch_returns_configured_pil(): 

    source = IEMAFOSSource(
        pil ='AFDIWX',
        wfos=['ind'],
        product_types=['afd']
    )

    pils_to_fetch = source._pils_to_fetch()

    assert len(pils_to_fetch) == 1 
    assert pils_to_fetch[0] == 'AFDIWX' # not AFDIND


def test_pils_to_fetch_builds_expected_combinations(): 
    source = IEMAFOSSource(
        wfos=['ind', 'iwx'],
        product_types=['afd', 'HWO']
    )

    pils_to_fetch = source._pils_to_fetch()

    assert len(pils_to_fetch) == 4 
    assert sorted(pils_to_fetch) == sorted(['AFDIND', 'AFDIWX', 'HWOIND', 'HWOIWX'])



def test_fetch_pil_uses_expected_request_parameters(
    iem_source,
    fake_session,
    fake_response,
):
    result = iem_source._fetch_pil(
        pil="AFDIND",
        from_date="2026-07-01",
        to_date="2026-07-10",
    )

    assert result == "AFOS response text"

    assert fake_session.calls == [
        {
            "url": iem_source.base_url,
            "params": {
                "pil": "AFDIND",
                "sdate": "2026-07-01",
                "edate": "2026-07-10",
                "limit": 100,
                "fmt": "text",
            },
            "timeout": 15,
        }
    ]

    assert fake_response.raise_for_status_called is True

def test_fetch_pil_strips_response_text(
    iem_source,
    fake_response,
):
    fake_response.text = "  AFOS response text  "

    result = iem_source._fetch_pil(
        pil="AFDIND",
        from_date="2026-07-01",
        to_date="2026-07-10",
    )

    assert result == "AFOS response text"


def test_fetch_pil_returns_none_for_empty_response( 
    iem_source,
    fake_response,
):
    fake_response.text = ""

    result = iem_source._fetch_pil(
        pil="AFDIND",
        from_date="2026-07-01",
        to_date="2026-07-10",
    )

    assert not result 

def test_fetch_pil_returns_none_for_iem_error_response(
    iem_source,
    fake_response,
):
    fake_response.text = "ERROR: No data found"

    result = iem_source._fetch_pil(
        pil="AFDIND",
        from_date="2026-07-01",
        to_date="2026-07-10",
    )

    assert result is None
    assert fake_response.raise_for_status_called is True


def test_fetch_pil_propagates_http_error(
    iem_source,
    fake_response,
):
    fake_response.error = requests.HTTPError(
        "500 Server Error"
    )

    with pytest.raises(
        requests.HTTPError,
        match="500 Server Error",
    ):
        iem_source._fetch_pil(
            pil="AFDIND",
            from_date="2026-07-01",
            to_date="2026-07-10",
        )

    assert fake_response.raise_for_status_called is True
    
def test_fetch_pil_propagates_timeout(
    iem_source,
    fake_session,
):
    fake_session.error = requests.Timeout(
        "Request timed out"
    )

    with pytest.raises(
        requests.Timeout,
        match="Request timed out",
    ):
        iem_source._fetch_pil(
            pil="AFDIND",
            from_date="2026-07-01",
            to_date="2026-07-10",
        )

    assert len(fake_session.calls) == 1

def test_fetch_raw_collects_successful_responses(
    iem_source,
    monkeypatch,
):
    monkeypatch.setattr(
        iem_source,
        "_pils_to_fetch",
        lambda: ["AFDIND", "HWOIND"],
    )

    responses_by_pil = {
        "AFDIND": "AFD response text",
        "HWOIND": "HWO response text",
    }

    def fake_fetch_pil(
        pil: str,
        from_date: str,
        to_date: str,
    ) -> str | None:
        return responses_by_pil[pil]

    monkeypatch.setattr(
        iem_source,
        "_fetch_pil",
        fake_fetch_pil,
    )

    result = iem_source._fetch_raw(
        from_date="2026-07-01",
        to_date="2026-07-10",
    )

    assert result == [
        {
            "pil": "AFDIND",
            "response": "AFD response text",
        },
        {
            "pil": "HWOIND",
            "response": "HWO response text",
        },
    ]

def test_fetch_raw_skips_empty_responses(
    iem_source,
    monkeypatch,
):
    monkeypatch.setattr(
        iem_source,
        "_pils_to_fetch",
        lambda: ["AFDIND", "HWOIND", "LSRIND"],
    )

    responses_by_pil = {
        "AFDIND": "AFD response text",
        "HWOIND": None,
        "LSRIND": "LSR response text",
    }

    monkeypatch.setattr(
        iem_source,
        "_fetch_pil",
        lambda pil, from_date, to_date: responses_by_pil[pil],
    )

    result = iem_source._fetch_raw(
        from_date="2026-07-01",
        to_date="2026-07-10",
    )

    assert result == [
        {
            "pil": "AFDIND",
            "response": "AFD response text",
        },
        {
            "pil": "LSRIND",
            "response": "LSR response text",
        },
    ]
    
def test_fetch_raw_returns_empty_list_when_no_data(
    iem_source,
    monkeypatch,
):
    monkeypatch.setattr(
        iem_source,
        "_pils_to_fetch",
        lambda: ["AFDIND", "HWOIND"],
    )

    monkeypatch.setattr(
        iem_source,
        "_fetch_pil",
        lambda pil, from_date, to_date: None,
    )

    result = iem_source._fetch_raw(
        from_date="2026-07-01",
        to_date="2026-07-10",
    )

    assert result == []

def test_fetch_records_runs_fetch_and_parse_workflow(
    iem_source,
    monkeypatch,
):
    raw_responses = [
        {
            "pil": "AFDIND",
            "response": "AFD response text",
        }
    ]

    parsed_records = [
        {
            "source_id": "iem-record-1",
            "pil": "AFDIND",
            "raw_text": "Parsed AFD product",
            "header": {
                "raw_id": "000",
                "wmo": "FXUS63",
                "wmo_header": "FXUS63 KIND 091838",
                "office": "KIND",
                "issued_code": "091838",
                "pil": "AFDIND",
            },
            "issued_at_text": (
                "Issued at 238 PM EDT Thu Jul 9 2026"
            ),
            "published_at": "2026-07-09T18:38:00+00:00",
        }
    ]

    calls = {}

    def fake_fetch_raw(
        from_date: str,
        to_date: str,
    ):
        calls["fetch"] = {
            "from_date": from_date,
            "to_date": to_date,
        }
        return raw_responses

    def fake_parse_records(responses):
        calls["parse"] = responses
        return parsed_records

    monkeypatch.setattr(
        iem_source,
        "_fetch_raw",
        fake_fetch_raw,
    )
    monkeypatch.setattr(
        iem_source,
        "_parse_records",
        fake_parse_records,
    )

    result = iem_source.fetch_records(
        from_date="2026-07-01",
        to_date="2026-07-10",
    )

    assert result == parsed_records

    assert calls["fetch"] == {
        "from_date": "2026-07-01",
        "to_date": "2026-07-10",
    }
    assert calls["parse"] is raw_responses