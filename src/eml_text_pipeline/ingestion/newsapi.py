import pandas as pd
from datetime import datetime
from .base import TextSource

class NewsAPISource(TextSource):

    name = "newsapi"
    source_type = "api"
    def fetch_raw(self):
        pass

    def parse_records(self, raw) -> pd.DataFrame:
        pass