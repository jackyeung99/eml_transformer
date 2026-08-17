from eml_transformer.sources.registry import register_source
from eml_transformer.sources.numeric.miso.client import MISOClient
from eml_transformer.sources.base import DataSource


@register_source("miso_load_forecast")
class MISOLoadForecastSource(DataSource):
    name = "miso_load_forecast"
    source_type = "numeric"
    ingestion_method = "api"
    update_mode = "incremental"
    supports_backfill = True



    def fetch_records(self, start = None, end = None):
        return super().fetch_records(start, end)


    def standardize_record(self, record):
        return super().standardize_record(record)