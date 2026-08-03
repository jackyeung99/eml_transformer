# Single-file sources
from eml_transformer.sources.text.newsapi import NewsAPISource
from eml_transformer.sources.text.gdelt import GDELTSource
from eml_transformer.sources.text.iem_afos import IEMAFOSSource

# Folder-based sources
# from eml_transformer.sources.text.gdelt.source import GDELTSource
# from eml_transformer.sources.text.iem_afos.source import IEMAFOSSource

__all__ = [
    "GDELTSource",
    "IEMAFOSSource",
    "NewsAPISource",
]